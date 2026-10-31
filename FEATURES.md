# JustUtter features: where each one comes from and why ours is better

For each feature:
- **Taken from:** the paid product that proved the idea, with a public source.
- **Why it matters:** the problem it solves for the user.
- **How JustUtter is better:** what we changed or improved.

JustUtter was **not** built by decompiling anyone's app. Wispr Flow's ToS §3A forbids it. Every feature is
reimplemented from public behaviour, using open-source parts (see `THIRD_PARTY_NOTICES.md`).

Price context:
- Wispr Flow Pro: $15/user/month ($180/yr), or $144/yr billed annually.
- Superwhisper Pro: $8.49/month.
- Willow Pro: $15/month.
- **JustUtter: $0, with no word cap, no account and no API key.**

| # | Feature | Taken from | Why it matters | How JustUtter is better | Status |
|---|---|---|---|---|---|
| 1 | **Hold-to-talk in any app** (hold Ctrl+Win, speak, release) | Wispr Flow: "Hold your dictation shortcut, speak, then release… Ctrl + Win on Windows" ([docs](https://docs.wisprflow.ai/articles/2772472373-what-is-flow)); Superwhisper ([site](https://superwhisper.com/)) | One gesture works everywhere, with no copy-pasting from a separate transcription window | Same gesture and default keys, but free with **no 2,000-words/week cap**, and you can remap it | Built |
| 2 | **On-device speech recognition** (Whisper via faster-whisper) | VoiceInk ([site](https://tryvoiceink.com/)), MacWhisper ([listing](https://goodsnooze.gumroad.com/l/macwhisper)) | Private, free, and works without internet | Wispr Flow states "An internet connection is required for transcription" ([docs](https://docs.wisprflow.ai/articles/2772472373-what-is-flow)). JustUtter **never sends audio anywhere** and works offline. It's also Windows-first, whereas VoiceInk and MacWhisper are Mac-only | Built |
| 3 | **Proof of local** (a network guard that blocks and counts connections, shown as "Network requests: 0") | New. Competitors' privacy is a promise or a settings toggle | People hesitate to dictate private work unless they can verify where the data goes | **Enforced and visible**: the app blocks its own outbound connections at runtime and shows the count. You can confirm it by dictating with Wi-Fi off | Built |
| 4 | **Filler-word removal and tidy punctuation** | Wispr "Formatting cleans up filler words, grammar, punctuation…" ([docs](https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-and-backtrack)); Willow; MacWhisper | Raw speech is full of "um"s and isn't usable as written text | **Deterministic and explainable**: every change is listed, the raw text is always kept, and nothing is rewritten by an opaque model | Built |
| 5 | **Spoken formatting commands** ("new line", "new paragraph", …) | Wispr Smart Formatting command list ([docs](https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-and-backtrack)) | Gives exact control over layout by voice | Same phrases, processed locally and predictably; covered by unit tests and evals | Built |
| 6 | **Backtrack ("scratch that")** | Wispr Backtrack: "actually", "scratch that", "never mind" ([docs](https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-and-backtrack)) | Lets you fix a mistake mid-sentence without retyping | Wispr's AI decides what to delete from context, which can surprise you. JustUtter uses an **explicit phrase with a fixed rule** (delete the previous clause), so it's predictable and never deletes meaning you didn't ask it to | Built |
| 7 | **Personal glossary** (names, jargon, acronyms) with recognition biasing | Wispr Dictionary ([docs](https://docs.wisprflow.ai/articles/2772472373-what-is-flow)); Aqua Voice dictionary ([API docs](https://aquavoice.com/api)); Dragon custom vocabulary | Errors on names and jargon are the #1 reason people give up on dictation | Stored **locally in plain JSON** that you can read, edit and export. Terms bias Whisper's decoding (`hotwords`) *and* exact replacements apply afterwards, and each replacement shows up in the history | Built |
| 8 | **Learn a correction from history** | Aqua "learned preferences"; Wispr dictionary learning | Fix a term once and it stays fixed | **You confirm every learned rule**, so it never silently locks in a mistake; the rule is visible and deletable | Built |
| 9 | **Snippets** (say "insert my email" to get static text) | Wispr Snippets ([pricing](https://wisprflow.ai/pricing)); Dragon AutoText/commands | Saves time on repeated text | **Static text only, never executed**, a deliberate security boundary (no voice-to-shell) | Built |
| 10 | **App-aware modes** (chat / email / dev / default) | Wispr Context Awareness (sorts apps into Email / Work / Personal / Other and reads on-screen text) ([docs](https://docs.wisprflow.ai/articles/4678293671-feature-context-awareness)) | A Slack message shouldn't read like an email, and code shouldn't get a trailing period | Uses **only the app name and window title**: it never reads your text fields or screen (Wispr's context can include textbox contents and on-screen text). The mode is shown, not guessed invisibly, and the mapping is editable | Built |
| 11 | **Undo AI edit, then paste the raw transcript** | Wispr "Undo AI edit" (open the Home tab → find the row → … → copy → paste manually) ([docs](https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-and-backtrack)) | Recovery is how users come to trust any automatic edit | **One hotkey (Ctrl+Alt+Z)** swaps the cleaned text for the raw transcript in place, replacing Wispr's 5-step manual process | Built |
| 12 | **Safe delivery**: blocked apps, a window-changed guard, and clipboard preserved | Wispr excludes password fields and banking apps from context ([docs](https://docs.wisprflow.ai/articles/4678293671-feature-context-awareness)) | You should never paste into the wrong window, and the app should never wipe what you copied | If the focused window changes mid-dictation, JustUtter **copies instead of pasting**. Password-manager apps are blocked by default. Your previous clipboard text is restored, or the text is typed out when the clipboard holds non-text data | Built |
| 13 | **"Didn't catch that" instead of guessing** | Inspired by Wispr's "If formatting fails, Flow pastes the unformatted transcript" | Silently inserting the wrong words is worse than inserting nothing | When Whisper's confidence is low or no speech is detected, **nothing is pasted** and the pill tells you | Built |
| 14 | **Savings and usage dashboard** | New | Makes the cost argument concrete for the user | Shows words dictated this week, how many words beyond Wispr's free cap, dollars saved against Wispr Pro, median latency and network requests | Built |
| 15 | **Fully open source** | Wispr Flow, Superwhisper and Willow are proprietary | Anyone can audit, fork and self-host it | **Apache-2.0** with notices; reproducible setup; every component's licence listed | Built |

## Added after the first live test (iteration 2)

| # | Feature | Taken from | Why it matters | How JustUtter is better | Status |
|---|---|---|---|---|---|
| 16 | **Hands-free long dictation** (Ctrl+Win+Space, finish with Ctrl+Win, cancel with Esc) | Wispr Flow hands-free mode ([docs](https://docs.wisprflow.ai/articles/2772472373-what-is-flow)) | Long messages without holding keys | Long recordings are **transcribed in ~20 s chunks while you talk** (cut at pauses), so finishing is fast even on a CPU. A live timer shows; the cap is 10 min | Built |
| 17 | **AI polish** (grammar, "Monday sorry Tuesday" → "Tuesday", stutters) | Wispr Smart Formatting / Backtrack, done in their cloud ([docs](https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-and-backtrack)) | Spoken grammar and self-corrections need more than rules | Runs a **local LLM** (qwen2.5:1.5b via Ollama on 127.0.0.1) at **0.68 s median**. **Every rewrite is validated**: questions stay questions (it can't "answer" you), instructions aren't obeyed, nothing new is added, names and glossary terms are kept. Anything suspicious falls back to the rule-based text. 10/10 adversarial evals pass | Built |
| 18 | **Personal memory** that improves with use | Wispr "Learns your names and jargon" ([pricing](https://wisprflow.ai/pricing)); Willow "smart memory" | Accuracy on *your* words and *your* style | Fully **local and inspectable**: learned words become Whisper hints, **Ctrl+Alt+L** learns from your own fixes (after you confirm), and your rewrites become style examples for the AI polish. View it in the dashboard; "Forget everything" deletes it | Built |
| 19 | **Never lose a dictation** | Lesson from our own first test (a 24 s dictation was silently dropped) | Trust | Every cancel shows its reason. A watchdog reads the real key state, so a lost key-release can't hang the recording. Clipboard restore waits for slow apps and never overwrites a newer copy | Built |

## Deliberately not copied (roadmap)
- **Cloud transcription or LLM:** possible as an opt-in "bring your own API key" mode, but it would add
  per-use costs and send audio off the device, so local stays the default.
- **Reading on-screen text for context:** a privacy cost JustUtter avoids by design.
- **Meeting notetaker, cloud sync, team dictionaries, mobile apps:** outside the hackathon scope.
