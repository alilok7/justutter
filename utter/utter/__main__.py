"""Command line: `python -m utter [run | download-model | eval]`."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from utter import APP_NAME
from utter.config import app_dir, load_settings, models_dir

log = logging.getLogger("utter")
MODELS = ("base.en", "small.en")


def setup_logging(verbose: bool = False) -> None:
    handlers: list[logging.Handler] = [logging.FileHandler(app_dir() / "utter.log",
                                                           encoding="utf-8")]
    if verbose:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def cmd_download(names: Sequence[str]) -> int:
    from faster_whisper import download_model

    for name in names:
        target = models_dir() / name
        print(f"Downloading {name} to {target} ...")
        try:
            download_model(name, output_dir=str(target))
        except Exception as exc:  # network/hub errors vary by library version
            log.exception("model download failed")
            print(f"Download of {name} failed: {exc}", file=sys.stderr)
            return 1
        print(f"  ok: {name}")
    return 0


def cmd_eval(names: Sequence[str]) -> int:
    from utter.evaluate import EVALS_DIR, run_model, summarise, to_markdown
    from utter.netguard import NetGuard
    from utter.transcriber import ModelMissingError, Transcriber

    settings, _ = load_settings()
    guard = NetGuard()
    guard.install()
    runs = {}
    try:
        for name in names:
            try:
                transcriber = Transcriber(name, models_dir())
            except ModelMissingError as exc:
                print(exc, file=sys.stderr)
                return 1
            transcriber.warmup()
            runs[name] = run_model(settings, transcriber)
            s = summarise(runs[name])
            print(f"{name}: WER {s['wer']:.1%}, median latency {s['median_latency_s']:.2f}s, "
                  f"checks {s['terms_ok']:.0%}")
    finally:
        guard.uninstall()
    out = EVALS_DIR / "results.md"
    out.write_text(to_markdown(runs, guard.blocked_count), encoding="utf-8")
    print(f"Network requests blocked during eval: {guard.blocked_count}")
    print(f"Wrote {out}")
    return 0


def cmd_eval_polish() -> int:
    import json
    import statistics

    from utter.evaluate import EVALS_DIR
    from utter.polish import Polisher

    settings, _ = load_settings()
    polisher = Polisher(settings.polish_model, timeout_s=10.0)
    problem = polisher.available()
    if problem:
        print(f"AI polish unavailable: {problem}", file=sys.stderr)
        return 1
    polisher.warmup()
    protected = [g.written for g in settings.glossary] + [s.text for s in settings.snippets]
    cases = json.loads((EVALS_DIR / "polish_cases.json").read_text(encoding="utf-8"))
    rows, latencies, passed, used = [], [], 0, 0
    for case in cases:
        result = polisher.polish(case["input"], protected)
        ok = all(t in result.text for t in case["must_contain"]) and not any(
            t in result.text for t in case["must_not_contain"])
        passed += ok
        used += result.used
        latencies.append(result.latency_s)
        out = result.text.replace("\n", "⏎").replace("|", "\\|")
        rows.append(f"| {case['id']} | {'pass' if ok else 'FAIL'} | "
                    f"{'polished' if result.used else 'fallback: ' + result.reason} | "
                    f"{result.latency_s:.2f}s | {out} |")
    summary = (f"{polisher.model}: {passed}/{len(cases)} pass, {used}/{len(cases)} polished, "
               f"median {statistics.median(latencies):.2f}s, max {max(latencies):.2f}s")
    print(summary)
    lines = ["# AI polish eval results", "", f"Local model via Ollama on 127.0.0.1. {summary}.",
             "Failing outputs are never silently inserted: a rejected rewrite falls back to the "
             "rule-based text.", "", "| Case | Result | Path | Latency | Output |",
             "|---|---|---|---:|---|", *rows]
    (EVALS_DIR / "polish_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if passed == len(cases) else 2


def cmd_run() -> int:
    from utter.app import main as run_app

    return run_app()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="utter", description=f"{APP_NAME}: local dictation")
    parser.add_argument("-v", "--verbose", action="store_true", help="also log to the console")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="start the dictation app (default)")
    dl = sub.add_parser("download-model", help="download Whisper models (one-time, needs internet)")
    dl.add_argument("models", nargs="*", choices=MODELS, default=list(MODELS))
    ev = sub.add_parser("eval", help="run speech evals and write evals/results.md")
    ev.add_argument("--model", action="append", choices=MODELS, dest="models")
    sub.add_parser("eval-polish", help="run AI polish evals (needs Ollama running)")
    args = parser.parse_args(argv)

    setup_logging(args.verbose)
    if args.command == "download-model":
        return cmd_download(args.models)
    if args.command == "eval":
        return cmd_eval(args.models or list(MODELS))
    if args.command == "eval-polish":
        return cmd_eval_polish()
    return cmd_run()


if __name__ == "__main__":
    sys.exit(main())
