# Project: AI dictation app (rebuild)

Rebuilding an AI dictation app, using reverse engineering of the original as the reference.
Research notes live in `AI_DICTATION_COMPETITIVE_RESEARCH.md`; the working code is under `utter/`.

## Process (follow in order)
1. Never write code first. Before each feature: (a) restate the goal, (b) list the files you will touch,
   (c) write acceptance criteria in `SPEC.md`. Wait for my OK on the plan.
2. Work in small tasks. Finish, test and commit each before starting the next.
3. If requirements are unclear, ask me. Do not guess.
4. If the original app behaves differently from the spec, update `SPEC.md` first, then the code.
5. Record what the original app does (features, settings, edge cases) in `SPEC.md` from evidence, not memory.

## Definition of done (all must be true before saying "done")
- Tests for the new behavior exist and the full suite passes. Show the output.
- Lint and type checks pass.
- You ran the feature and checked the real result. Compiling is not proof it works.
- No unrelated files were changed.

## Reliable output
- Validate every external input and model output with a typed schema (Pydantic / Zod or equivalent).
- Handle errors explicitly. No empty catch blocks, no silent failures.
- Retries with limits for network/API calls. Make repeated actions safe to repeat.
- Log key steps so failures can be traced.
- For AI steps (speech-to-text, cleanup, rewriting): keep a fixed set of example inputs and expected
  outputs (evals) and re-run them after every prompt or model change.
- If confidence is low, fall back to a safe default or ask the user. Never insert guessed text silently.

## Style
- Match existing code style. Simple over clever.
- Do not add dependencies without asking.

## Commands
All commands run from `utter/` (Python 3.12, Windows).
- Install: `python -m venv .venv` then `.venv\Scripts\python -m pip install -e .[dev]`, then
  `.venv\Scripts\python -m utter download-model` (one-time, needs internet)
- Run: `run.bat` or `.venv\Scripts\python -m utter`
- Test: `.venv\Scripts\python -m pytest -q`
- Evals: `.venv\Scripts\python -m utter eval` (speech clips: `powershell -File evals\make_audio.ps1` first)
- Lint/typecheck: `.venv\Scripts\ruff check .` and `.venv\Scripts\mypy utter`
