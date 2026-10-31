"""Speech evals: word error rate, glossary hits and latency on fixed local clips."""

from __future__ import annotations

import json
import logging
import re
import statistics
import wave
from datetime import date
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field

from utter.cleanup import clean
from utter.config import Mode, Settings
from utter.transcriber import SAMPLE_RATE, Transcriber

log = logging.getLogger(__name__)

EVALS_DIR = Path(__file__).resolve().parent.parent / "evals"


class SpeechCase(BaseModel):
    id: str
    say: str
    reference: str
    must_contain: list[str] = Field(default_factory=list)
    must_not_contain: list[str] = Field(default_factory=list)


class CaseResult(BaseModel):
    id: str
    raw: str
    clean: str
    wer: float
    latency_s: float
    audio_s: float
    terms_ok: bool
    confident: bool


def normalise(text: str) -> list[str]:
    text = re.sub(r"[^a-z0-9' ]+", " ", text.lower().replace("-", " "))
    return text.split()


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref, hyp = normalise(reference), normalise(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wav:
        if wav.getframerate() != SAMPLE_RATE or wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError(f"{path.name}: expected 16 kHz mono 16-bit PCM")
        frames = wav.readframes(wav.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def load_cases() -> list[SpeechCase]:
    data = json.loads((EVALS_DIR / "speech_cases.json").read_text(encoding="utf-8"))
    return [SpeechCase.model_validate(c) for c in data]


def run_model(settings: Settings, transcriber: Transcriber) -> list[CaseResult]:
    audio_dir = EVALS_DIR / "audio"
    hotwords = [g.written for g in settings.glossary]
    results: list[CaseResult] = []
    for case in load_cases():
        wav = audio_dir / f"{case.id}.wav"
        if not wav.exists():
            raise FileNotFoundError(f"{wav} missing; run evals\\make_audio.ps1 first")
        tr = transcriber.transcribe(read_wav(wav), hotwords, settings.no_speech_threshold,
                                    settings.logprob_threshold)
        cleaned = clean(tr.text, Mode.DEFAULT, settings.glossary, settings.snippets)
        terms_ok = all(t in cleaned.clean for t in case.must_contain) and not any(
            t in cleaned.clean for t in case.must_not_contain
        )
        results.append(CaseResult(
            id=case.id, raw=tr.text, clean=cleaned.clean,
            wer=word_error_rate(case.reference, tr.text), latency_s=tr.latency_s,
            audio_s=tr.audio_s, terms_ok=terms_ok, confident=tr.confident,
        ))
    return results


def summarise(results: list[CaseResult]) -> dict[str, float]:
    return {
        "wer": statistics.mean(r.wer for r in results),
        "median_latency_s": statistics.median(r.latency_s for r in results),
        "max_latency_s": max(r.latency_s for r in results),
        "terms_ok": sum(r.terms_ok for r in results) / len(results),
        "confident": sum(r.confident for r in results) / len(results),
    }


def to_markdown(runs: dict[str, list[CaseResult]], blocked_requests: int) -> str:
    lines = [
        "# Speech eval results",
        "",
        f"Run on {date.today().isoformat()} on the demo laptop (CPU only, int8). Clips are "
        "generated locally by Windows text-to-speech (`evals/make_audio.ps1`); the network guard "
        f"was active and blocked **{blocked_requests}** outbound requests.",
        "",
        "WER compares the *raw* transcript with a plain spoken reference "
        "(e.g. `mera lion`, `n u s`). Glossary hotwords often make Whisper write the intended "
        "form (`MERaLiON`, `NUS`) directly, which counts as a WER error even though the final "
        "text is correct; the checks column tests the final cleaned text.",
        "",
        "| Model | Mean WER | Median latency | Max latency | Glossary/command checks | Confident |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, results in runs.items():
        s = summarise(results)
        lines.append(f"| {name} | {s['wer']:.1%} | {s['median_latency_s']:.2f}s | "
                     f"{s['max_latency_s']:.2f}s | {s['terms_ok']:.0%} | {s['confident']:.0%} |")
    for name, results in runs.items():
        lines += ["", f"## {name}", "", "| Case | WER | Latency | Checks | Clean output |",
                  "|---|---:|---:|:---:|---|"]
        for r in results:
            out = r.clean.replace("\n", "⏎").replace("|", "\\|")
            lines.append(f"| {r.id} | {r.wer:.0%} | {r.latency_s:.2f}s | "
                         f"{'pass' if r.terms_ok else 'FAIL'} | {out} |")
    return "\n".join(lines) + "\n"
