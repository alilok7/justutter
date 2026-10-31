# Speech eval results

Run on 2026-10-31 on the demo laptop (CPU only, int8). Clips are generated locally by Windows text-to-speech (`evals/make_audio.ps1`); the network guard was active and blocked **0** outbound requests.

| Model | Mean WER | Median latency | Max latency | Glossary/command checks | Confident |
|---|---:|---:|---:|---:|---:|
| base.en | 7.8% | 0.58s | 0.68s | 100% | 100% |
| small.en | 7.8% | 1.69s | 1.90s | 100% | 100% |

## base.en

| Case | WER | Latency | Checks | Clean output |
|---|---:|---:|:---:|---|
| s01-plain | 0% | 0.68s | pass | Hey team, the design review is moved to tomorrow afternoon. |
| s02-question | 0% | 0.61s | pass | Can you send me the slides before the meeting? |
| s03-glossary | 18% | 0.58s | pass | We tested the MERaLiON model and the results look promising. |
| s04-acronym | 38% | 0.55s | pass | I study computer science at NUS. |
| s05-glossary-github | 22% | 0.63s | pass | Please push the latest changes to GitHub tonight. |
| s06-paragraph | 0% | 0.58s | pass | Thanks for coming.⏎⏎The next steps are listed below. |
| s07-backtrack | 0% | 0.59s | pass | The demo is on Tuesday. |
| s08-plain | 0% | 0.52s | pass | Let me know if you have any questions about the project. |
| s09-plain | 0% | 0.53s | pass | Our hackathon project runs entirely on the laptop without internet. |
| s10-list | 0% | 0.54s | pass | Remember to buy milk, eggs and bread on the way home. |

## small.en

| Case | WER | Latency | Checks | Clean output |
|---|---:|---:|:---:|---|
| s01-plain | 0% | 1.69s | pass | Hey team, the design review is moved to tomorrow afternoon |
| s02-question | 0% | 1.55s | pass | Can you send me the slides before the meeting? |
| s03-glossary | 18% | 1.72s | pass | We tested the MERaLiON model and the results look promising. |
| s04-acronym | 38% | 1.74s | pass | I study Computer Science at NUS |
| s05-glossary-github | 22% | 1.69s | pass | Please push the latest changes to GitHub tonight. |
| s06-paragraph | 0% | 1.63s | pass | Thanks for coming!⏎⏎The next steps are listed below. |
| s07-backtrack | 0% | 1.63s | pass | The demo is on Tuesday. |
| s08-plain | 0% | 1.60s | pass | Let me know if you have any questions about the project. |
| s09-plain | 0% | 1.90s | pass | Our Hackathon project runs entirely on the laptop without internet |
| s10-list | 0% | 1.81s | pass | Remember to buy milk, eggs and bread on the way home. |
