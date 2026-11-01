# Speech eval results

Run on 2026-11-02 on the demo laptop (CPU only, int8). Clips are generated locally by Windows text-to-speech (`evals/make_audio.ps1`); the network guard was active and blocked **0** outbound requests.

WER compares the *raw* transcript with a plain spoken reference (e.g. `mera lion`, `n u s`). Glossary hotwords often make Whisper write the intended form (`MERaLiON`, `NUS`) directly, which counts as a WER error even though the final text is correct; the checks column tests the final cleaned text.

| Model | Mean WER | Median latency | Max latency | Glossary/command checks | Confident |
|---|---:|---:|---:|---:|---:|
| small.en | 7.8% | 2.47s | 708.61s | 100% | 100% |

## small.en

| Case | WER | Latency | Checks | Clean output |
|---|---:|---:|:---:|---|
| s01-plain | 0% | 1.81s | pass | Hey team, the design review is moved to tomorrow afternoon |
| s02-question | 0% | 2.26s | pass | Can you send me the slides before the meeting? |
| s03-glossary | 18% | 2.48s | pass | We tested the MERaLiON model and the results look promising. |
| s04-acronym | 38% | 2.28s | pass | I study Computer Science at NUS |
| s05-glossary-github | 22% | 708.61s | pass | Please push the latest changes to GitHub tonight. |
| s06-paragraph | 0% | 2.82s | pass | Thanks for coming!⏎⏎The next steps are listed below. |
| s07-backtrack | 0% | 2.53s | pass | The demo is on Tuesday. |
| s08-plain | 0% | 2.42s | pass | Let me know if you have any questions about the project. |
| s09-plain | 0% | 2.60s | pass | Our Hackathon project runs entirely on the laptop without internet |
| s10-list | 0% | 2.46s | pass | Remember to buy milk, eggs and bread on the way home. |
