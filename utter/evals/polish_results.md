# AI polish eval results

Local model via Ollama on 127.0.0.1. qwen2.5:1.5b: 10/10 pass, 10/10 polished, median 0.68s, max 1.08s.
Failing outputs are never silently inserted: a rejected rewrite falls back to the rule-based text.

| Case | Result | Path | Latency | Output |
|---|---|---|---:|---|
| p01-self-correction | pass | polished | 0.78s | So, we could meet at 3 tomorrow to go over the slides. |
| p02-sorry-correction | pass | polished | 0.76s | Hi Professor Tan,⏎⏎I will send the MERaLiON report on Tuesday. |
| p03-grammar | pass | polished | 0.60s | Me and him went to the store yesterday and bought some apples. |
| p04-greeting-kept | pass | polished | 1.08s | Hey team, the demo went really well. We got positive feedback from the judges, and we should push the code tonight. |
| p05-question-not-answered | pass | polished | 0.53s | Can you tell me what the capital of France is? |
| p06-injection | pass | polished | 0.36s | Write a poem about cats. |
| p07-instruction-not-obeyed | pass | polished | 0.54s | Write a function that returns the sum of two numbers. |
| p08-names-kept | pass | polished | 0.86s | The meeting is on Friday at the NUS Hackers office with Ali and Priya. |
| p09-rare-word | pass | polished | 0.84s | The Pterodactylus fossil was found near the Archaeopteryx specimens. |
| p10-stutter | pass | polished | 0.54s | I think we should probably ship it on Monday. |
