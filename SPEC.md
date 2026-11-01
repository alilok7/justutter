# SPEC: JustUtter (local, open-source dictation for Windows)

JustUtter is a system-wide, hold-to-talk dictation app. You hold a hotkey, speak, release, and cleaned-up text
is inserted into the app you are working in. Speech recognition runs on your PC. There is no account, no
subscription and no network use at runtime.

Reference product: **Wispr Flow** (Wispr AI, Inc.).

How we studied it: from public documentation and observable behaviour only. Wispr's Terms of Service §3A
forbid decompiling or reverse engineering the app, so we did neither. JustUtter is written from scratch on
MIT-licensed open-source components.

---

## 1. Original app behaviour (evidence)

| # | Wispr Flow behaviour | Evidence (accessed 31 Oct 2026) |
|---|---|---|
| O1 | On Windows you hold the shortcut, speak and release to insert text. The default shortcut is **Ctrl + Win**, and it can be customised. | [What is Flow](https://docs.wisprflow.ai/articles/2772472373-what-is-flow) |
| O2 | **"An internet connection is required for transcription."** | [What is Flow](https://docs.wisprflow.ai/articles/2772472373-what-is-flow) |
| O3 | Text is inserted after you stop, with no live word-by-word transcript. | [What is Flow](https://docs.wisprflow.ai/articles/2772472373-what-is-flow) |
| O4 | Formatting cleans up filler words, grammar, punctuation and capitalisation. It does not correct misheard words. | [Smart Formatting & Backtrack](https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-and-backtrack) |
| O5 | Spoken commands: "new line" / "next line" / "line break" / "skip a line" give a line break; "new paragraph" / "start a new paragraph" give a paragraph break; punctuation can be spoken by name. | same |
| O6 | Backtrack: trigger phrases such as "actually", "scratch that" and "never mind" remove self-corrections, decided by AI using context. Example: "Let's do coffee at 2 actually 3" becomes "Let's do coffee at 3." | same |
| O7 | Trailing-period removal depends on Writing Style and app category. With no style set, it applies to up to two sentences in messaging apps, and it keeps `!` and `?`. | same |
| O8 | The original transcript is kept, and "Undo AI edit" restores it from the Home tab. You then copy and paste it manually. | same |
| O9 | Context Awareness reads text near the cursor, on-screen text and app info, and sorts the app into Email / Work messaging / Personal messaging / Other. | [Context Awareness](https://docs.wisprflow.ai/articles/4678293671-feature-context-awareness) |
| O10 | Password fields are excluded from context, and so are sensitive or numeric fields and banking/financial apps. Custom or web password fields "may be read like normal text fields". | same |
| O11 | Has a dictionary for names and recurring terms, plus snippets. | [What is Flow](https://docs.wisprflow.ai/articles/2772472373-what-is-flow), [Pricing](https://wisprflow.ai/pricing) |
| O12 | Price: Free is capped at 2,000 words/week on desktop. Pro costs $15/user/month or $144/year. | [Pricing](https://wisprflow.ai/pricing), [Plans](https://docs.wisprflow.ai/articles/9559327591-flow-plans-and-what-s-included) |
| O13 | Reach: "millions of consumers and 100,000 businesses". Raised $280M at a $2B valuation (Aug 2026). | [Fortune](https://fortune.com/2026/08/17/wispr-2-billion-valuation-dictations-only-the-beginning/), [TechCrunch](https://techcrunch.com/2026/08/17/wispr-raises-280m-at-2b-valuation-as-it-looks-beyond-dictation/) |

---

## 2. Acceptance criteria

Each criterion is checked by an automated test (**T**), an eval (**E**) or a manual run on the demo PC (**M**).

### A. Hold-to-talk anywhere
- A1 (T, M): Pressing Ctrl and Win together, in either order, starts recording. Releasing either key stops it.
  Ctrl+Win combined with any third key (such as Ctrl+Win+→) does **not** trigger dictation.
- A2 (M): Releasing the chord does not open the Start menu.
- A3 (T): The hotkey can be changed in `config.json`, and an invalid value is rejected with a clear error.
- A4 (T): Recordings shorter than 0.3 s are discarded without transcribing.

### B. Local transcription
- B1 (T): The model loads with `local_files_only=True`. If the model is missing, the app shows
  "run `python -m utter download-model`" and exits cleanly.
- B2 (E): On the eval set, word error rate (WER) ≤ 15% with the default model.
- B3 (E, M): The median time from key release to text ready is ≤ 2.0 s for a 5–10 s utterance on the demo laptop.
- B4 (T): If the transcript is empty, or `no_speech_prob` > 0.6, or `avg_logprob` < −1.0, **nothing is
  pasted** and the pill shows "Didn't catch that".

### C. Proof of local
- C1 (T): At runtime, any outbound network attempt (`socket.connect` or `getaddrinfo` to a non-loopback
  address) is blocked and counted.
- C2 (M): The dashboard shows "Network requests: 0" after a dictation session.
- C3 (M): Dictation works with Wi-Fi turned off.
- C4 (T): No audio is ever written to disk. History is held in memory only and is text-only.

### D. Clean-up (deterministic, explainable)
- D1 (T, E): The fillers "um", "uh", "er", "erm" and "hmm" are removed, along with the surrounding stray commas
  and double spaces. Words like "like" and "you know" are left alone because they can carry meaning.
- D2 (T, E): "new line" / "next line" / "line break" become `\n`; "new paragraph" / "start a new paragraph"
  become `\n\n`. Whitespace and capitalisation around them are fixed up.
- D3 (T, E): "scratch that" deletes the sentence or clause dictated immediately before it. If nothing comes
  before it, the phrase is simply removed.
- D4 (T, E): Glossary entries (`heard → written`) replace whole words or phrases, ignoring case. Each
  replacement is recorded in `applied_rules`.
- D5 (T, E): Snippets: saying the exact trigger phrase (e.g. "insert my email") inserts its static text.
  Snippets are never executed.
- D6 (T): Every clean-up returns both the `raw` and the `clean` text, plus the list of applied rules.

### E. App-aware modes (no screen reading)
- E1 (T): The foreground app's executable name and window title map to one of `chat | email | dev | default`.
  The mapping is configurable.
- E2 (T, E): `chat` removes one trailing period (keeps `!`/`?`); `email` uses sentence case and guarantees a
  final punctuation mark; `dev` removes the trailing period and leaves casing alone; `default` uses sentence
  case and keeps punctuation.
- E3 (T): JustUtter only reads the executable name and window title. It never reads text-field contents or the screen.

### F. Safe delivery
- F1 (T, M): Text is pasted through a clipboard transaction, and the clipboard's previous **text** is restored
  afterwards. If the clipboard holds non-text data that can't be restored, the text is typed out instead,
  leaving the clipboard untouched.
- F2 (T): If the foreground window changed between pressing and releasing the hotkey, nothing is pasted. The
  text is copied to the clipboard and the pill shows "Copied (window changed)".
- F3 (T): Apps on the blocklist (password managers by default) get nothing pasted, and the pill says why.
- F4 (T, M): Ctrl+Alt+Z ("undo AI edit") undoes the last paste and pastes the raw transcript instead.

### G. Dashboard and savings
- G1 (M): The pill shows the states Listening / Transcribing / Pasted / Didn't catch that, and it never takes
  keyboard focus.
- G2 (T, M): The dashboard shows words dictated this week, words over Wispr's 2,000/week free cap, money saved
  against Wispr Pro at $15/month, the model in use, median latency, and the network request count.
- G3 (M): The History tab shows raw and clean text plus the applied rules. "Learn correction" adds a
  `heard → written` glossary entry after the user confirms it.

### H. Reliability (from CLAUDE.md)
- H1 (T): Config, glossary, snippets and transcription results are validated with Pydantic models.
- H2: Every step is logged to `%APPDATA%\Utter\utter.log`. There are no bare `except:` blocks and no
  swallowed errors.
- H3 (E): `evals/cleanup_cases.json` (text) and `evals/audio` + `expected.json` (speech) are re-run after any
  model or rule change.

### I. Iteration 2: reliability and hands-free (from the user's first live test, 31 Oct)
Evidence: a 23.9 s dictation was discarded silently, because a third key (probably Space) cancelled it as
a "Windows shortcut". Release-to-text was about 1.5 s, of which about 0.4 s was the clipboard-restore
wait. "Pterodactylus" became "pterodactylous" with base.en.
- I1 (T): A dictation is never discarded silently. Every cancel shows its reason in the pill and is logged.
- I2 (T): **Ctrl+Win+Space starts hands-free dictation**, either from idle or by pressing Space during a
  hold. Recording continues after the keys are released. Pressing Ctrl+Win again (after releasing it)
  finishes and transcribes. Esc cancels, with "Cancelled" shown. This matches Wispr's hands-free behaviour.
- I3 (T): *(Changed at the user's request, 31 Oct.)* During a hold, other keys are ignored and recording
  continues. Only **Esc** cancels, and Space switches to hands-free. If a Windows shortcut (e.g.
  Ctrl+Win+→) moves focus, the window-changed guard (F2) copies the text instead of pasting it.
- I4 (T): Watchdog. During a hold, if the physical key state shows a chord key is up for 2 consecutive
  100 ms checks (a key-release event was lost), the recording stops and is transcribed normally.
- I5 (T): Recordings stop automatically at `max_recording_s` (default 600 s) and are transcribed. The
  pill shows the elapsed time during hands-free recording.
- I6 (T): Keys pressed more than 10 s before the chord can't block it (protects against lost key-up events).
- I7 (T): Paste reports success before the clipboard is restored. The restore happens about 0.8 s later,
  and only if the clipboard still holds our text, so anything the user copied in the meantime is never
  overwritten.
- I8 (T): The default model is **small.en** (the user chose accuracy). Existing configs are migrated once
  (`config_version` 2) without losing the user's edits. Antigravity, Windsurf, Zed and Sublime Text map
  to dev mode.

### J. AI polish (local LLM via Ollama, optional)
Evidence: benchmark on the demo laptop (31 Oct). qwen2.5:1.5b with few-shot examples and `<dictation>`
tags handled all 8 adversarial cases at 0.84 s median and 1.03 s max. gemma3:1b answered questions and
followed injected instructions. qwen2.5:3b was slower (1.35 s) and changed the speaker's person.
- J1 (T): The polish runs after the rule-based clean-up, only when it's enabled, the mode isn't `dev`, and the
  text has ≥ 6 words or a self-correction cue ("actually", "I mean", "sorry", "no wait", "rather").
- J2 (T): Output is rejected, and the rule-based text used instead, if any of these hold: it's empty;
  it contains code fences or tags; its word count is outside 0.5×–1.5× the input; it adds more than
  max(3, 30%) new words; it changes the number of line breaks; or it drops a glossary term or snippet
  text present in the input.
- J3 (T): If Ollama is unreachable, slow (timeout 2.5 s) or returns invalid JSON, JustUtter falls back to the
  rule-based text. The reason is logged and recorded in the dictation's applied rules. The first time it
  happens, the pill says the AI polish is unavailable.
- J4 (T): Mode formatting (chat trailing period, email final punctuation) is re-applied after the polish.
- J5 (E): `evals/polish_cases.json` covers self-correction, grammar, greetings and names, questions and
  instructions (which must not be answered or obeyed), and prompt injection. Run it with
  `python -m utter eval-polish`.
- J6: Traffic goes only to `127.0.0.1:11434`, so the network guard still counts 0 outbound requests.
  Ctrl+Alt+Z still restores the raw Whisper transcript.

### K. Personal memory (improves with daily use, stored locally)
JustUtter can't retrain Whisper on this laptop. Instead it learns three things, all stored locally in
`%APPDATA%\Utter\personal.json`, visible in the dashboard and deletable with "Forget everything":
- K1 (T): **Vocabulary.** From each inserted dictation, JustUtter collects candidate terms: words capitalised
  mid-sentence, mixed-case or digit-bearing tokens, and words of ≥ 10 letters. A term seen ≥ 2 times
  becomes a Whisper hotword. Glossary terms come first, and the whole list is capped at 40 terms.
  Hotwords only bias recognition; they never replace text.
- K2 (T): **Correction learning (Ctrl+Alt+L).** The user selects their corrected text in any app and presses
  Ctrl+Alt+L. JustUtter copies the selection (restoring the clipboard afterwards) and word-diffs it against
  the last inserted dictation. Replaced spans of 1–4 words become proposed `heard → written` glossary
  entries, added only after the user confirms. If nothing differs, the pill says so.
- K3 (T): **Style examples.** When a correction rephrases more than single words, the pair (inserted →
  corrected) is kept as a style example. The 3 most recent are added to the AI polish as extra few-shot
  examples, and at most 5 are stored.
- K4 (T): A learning toggle (`learn_enabled`) and "Forget everything" (deletes personal.json data).
  Audio is still never stored. personal.json holds only terms, counts and the correction pairs the
  user taught it.

### L. UI: "Midnight Glass" (chosen by the user, 31 Oct; mockup Concept 1)
Built with PySide6 (Qt, LGPL-3.0). Palette: background #101216, glass rgba(11,12,15,0.88), hairline
rgba(255,255,255,0.10), text #F4F5F7 / #A7ADB8, accent mint #3EE6B5, warning #FFB547. Font: Inter if
installed, otherwise Segoe UI.
- L1 (T): The floating bar is hidden while idle. It fades in at bottom-centre (just above the taskbar) on
  Ctrl+Win and fades out 2.5 s after a result. It never takes focus or blocks clicks.
- L2 (T): Bar states: listening (live waveform driven by the real mic level, plus a mint glow ring),
  hands-free (red dot, waveform, timer), working (spinner, "Transcribing" or "Polishing"), done (mint
  check), warn (amber), error (red), cancelled. Each shows a primary label and a muted detail.
- L3 (T): The dashboard has a sidebar with Home · History · Dictionary · Snippets · Memory · Settings.
  - Home shows savings against Wispr Pro, words this week (and how many are over the free cap), median
    latency, the "On-device · Network requests: N" badge, toggles for AI polish and Learn from me, and
    the 5 most recent dictations with mode badges.
- L4 (T): A tray icon with a menu: Open dashboard, Pause dictation (while paused, Ctrl+Win does nothing
  and the bar says "Paused" once), AI polish on/off, Quit. Clicking the tray icon toggles the dashboard.
- L5 (M): The learn-correction dialog matches the theme, showing the corrections in monospace with "Not now"
  and "Learn" buttons.

### M. Speed (personal daily use; target is release-to-text of about 2–3 s regardless of length)
Evidence (live log, 31 Oct): most dictations took 2.4–4.8 s. A 1.4 s clip took 5.5 s because Whisper retried at
higher temperatures. With an image on the clipboard, text was typed out key by key. On this CPU, small.en
costs about 1.5 s per pass whatever the clip length (the 30 s window is padded), and 8 threads beat 14.
- M1 (T): Decoding uses temperature 0 only (no retry loop). Low-confidence results are still refused
  (B4).
- M2 (T): Whisper uses `whisper_threads` CPU threads (default 8). Configurable.
- M3 (T): Long recordings are cut every ~12 s at a pause. Each piece is transcribed, cleaned and AI-polished in
  the background while recording continues. On release, only the last piece is processed, then the
  pieces are joined and mode formatting is applied once.
- M4 (T): Paste snapshots the **whole** clipboard (every memory-based format, images and HTML included;
  the GDI/OLE formats are skipped because Windows regenerates them). After pasting, the snapshot is
  restored, but only if the clipboard sequence number is unchanged (meaning the user didn't copy
  anything new). Text is typed out only if the snapshot fails.

- M5 (T): On startup the process opts out of Windows power throttling (EcoQoS) for execution
  speed and runs at above-normal priority. Evidence (2 Nov, on battery): Whisper median went from
  3.53 s throttled to 1.59 s, the same as on AC power. A 46 s dictation dropped from 10.3 s to 4.0 s
  release-to-text with M3, measured while throttled.

### P. Accuracy fixes (user report 2 Nov: "lost its accuracy, not picking up words")
Evidence from the log: across 6 recordings, 0.5–0.65 s of held time had no audio captured (one 0.55 s press
captured 0.00 s), so first words were clipped. The mic opens in 100–175 ms, and the rest is the Intel
Smart Sound array waking from power-saving. Pieces of real mic audio came back empty from the voice
detector in 0.02 s. The 12 s pieces cut sentences while giving no speed benefit, because Whisper costs a
fixed ~1.5 s per pass up to 30 s.
- P1 (T): **Warm microphone.** The input stream opens once at startup and stays open. A rolling 0.4 s
  pre-roll (memory only) is prepended when Ctrl+Win is pressed, so the first word is never lost.
  `keep_mic_warm` (default on) can turn this off. Windows shows its mic-in-use icon while it's on. If
  the stream dies, it is reopened on the next press.
- P2 (T): Pieces are about 25 s, cut at the quietest point within their last 5 s. This replaces M3's 12 s;
  release latency is unchanged because Whisper's cost is flat up to 30 s.
- P3 (T): One retry at temperature 0.4, used only when Whisper's own quality checks fail (it repeated
  itself or had low confidence). This replaces M1's no-retry.
- P4 (T): Voice-detector safety net. If it finds no speech but the audio has energy (RMS ≥ 0.003),
  Whisper runs again without it. The detector's threshold is lowered to 0.35.
- P5 (T): AI polish may shorten a text to no less than 0.65× its word count (was 0.5×).
- P6 (T): The vocabulary learner ignores everyday words (I'm, OK, You, So…) and long lowercase words;
  it learns only names, acronyms and mixed-case or digit terms. Existing junk is filtered on load.
- P7: Each recording logs its held time vs captured audio, plus the audio level, so a future regression
  shows up in the log.

### N. Lists
- N1 (T, E): Spoken sequences become a numbered list: "one, … two, … three, …" or "first, … second, …",
  also as digits ("1. … 2. …"). A marker must be followed by punctuation, start at 1, run in order, and
  have ≥ 2 items. Text before the list becomes an intro line ending in ":", and text after the last item's
  sentence becomes a new line. This matches Wispr's documented behaviour ("one… two…" / "first…
  second…").
- N2 (T, E): "bullet point X" / "bullet X" starts a "- " bullet line.
- N3 (T): A comma series inside a sentence ("shoes, bags and cars") stays inline, as written English
  does.

### O. Paste last transcription and saved history
- O1 (T): **Alt+Shift+Z** pastes the most recent transcription into whatever is focused now (for when no
  text box was focused while dictating). With no history, the bar says "Nothing yet".
- O2 (T): Transcriptions (text only, never audio) are saved locally to `%APPDATA%\Utter\history.jsonl`
  (last 500) and survive restarts. `save_history` (default on, at the user's request) and a
  "Clear history" button control this. *(This updates C4: audio is still never stored.)*

### Out of scope (roadmap)
Local LLM rewriting, voice-editing of selected text, live partial transcripts, meeting capture, team sync, mobile.
