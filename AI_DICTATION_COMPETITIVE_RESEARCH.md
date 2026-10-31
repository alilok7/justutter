# AI Dictation: Competitive Research and Feature Strategy

**Research date:** 31 October 2026  
**Scope:** product/market and technical research only. This report does not modify or propose implementation of application code. Prices and feature availability change frequently; prices below are the publicly displayed figures captured from the linked first-party pages where available.

## Executive summary

Build **OpenFlow** (working title): an open-source, Windows-first, local-first system-wide dictation tool. A user holds a global hotkey, speaks naturally in any focused text field, and receives paste-ready text that respects the writing surface (for example, terse Slack, a professional email, or a code comment). The MVP must make its privacy and cost model visible: audio stays on-device, no account or API key is required, and the app is free under Apache-2.0.

This is not a proposal to clone a proprietary product. It is a lawful feature-level reimplementation based on public behavior and permissively licensed building blocks. The competitive insight is that paid products have proved the interaction model—global push-to-talk + cleanup + personalization—while the open stack now makes a credible $0 local alternative possible.

### Recommendation in one sentence

For the hackathon, recreate the *felt magic* of Wispr Flow/Superwhisper (dictate anywhere, clean prose) and combine it with the local transparency of VoiceInk/MacWhisper, then add a highly visible **“why did it write that?” correction loop** that teaches a local dictionary without transmitting text.

### What to prioritize

1. **Working system-wide push-to-talk and paste** — the demo-critical base.
2. **Fast local speech-to-text with an explicit offline indicator** — the cost/privacy proof.
3. **Clean-up modes plus safe, reversible preview** — the quality differentiator.
4. **Personal glossary and one-tap correction learning** — a memorable product detail, especially for Singaporean names, code, course acronyms, and mixed technical vocabulary.
5. **Context-aware formatting with consent and redaction** — high-impact only if it works reliably; do not silently read sensitive fields.

The strongest demo is a three-surface “same voice, appropriate output” story: dictate a casual Slack update, a formal email, and a technical terminal/code comment; show correct niche terms from the glossary; then open the local-only activity pane proving the audio/text never left the device. This directly supports the rubric’s two largest criteria: a cool working build (25%) and quantified cost reduction (25%).

---

## 1. Project and hackathon grounding

### Repository assessment

At research time the repository contains two source documents, not an existing application or README:

| Item | Finding | Consequence |
|---|---|---|
| `Autonomous SG 2026_NUS_Hackers.md` | Official problem statement and rubric | This is the governing competition source. |
| `youtube-XzjSx7u9mGw.md` | Transcript/notes for an unrelated AI customer-support course | It does not impose product or technical constraints for this dictation project. |
| Application code/dependencies/tests | None found | Do not claim an existing architecture; choose one intentionally during implementation. |

### Confirmed requirements from the official problem statement

The [official problem statement](Autonomous%20SG%202026_NUS_Hackers.md) asks teams to select an opaque, cool/useful app, service, device, or system; understand how it works; then build a better, inexpensive, open-source version. It specifies five independently scored criteria (1–5 each), total weight 100%:

| Confirmed criterion | Weight | What evidence judges explicitly want | Product consequence |
|---|---:|---|---|
| Cost of the status quo | 20% | Named target and credible, sourced price/cost | Name paid dictation subscriptions and show their current prices. |
| Reach of the old thing | 15% | Users, downloads, market share, or another credible signal | Use product scale evidence cautiously; do not invent market share. |
| Coolness of the new build | 25% | A live, impressive, polished working build | The system-wide hotkey interaction must work on stage. |
| Cost reduction | 25% | Clear before/after, preferably free/near-free | Compare recurring paid subscription with $0 software/API cost for local mode. |
| Open-source licensing | 15% | Public reusable repo with an explicit licence | Ship a public repo, `LICENSE`, notices, reproducible build steps, and a permissive licence. |

The document says judges ask, “What did you uncover, and how do you know it works?” This report therefore marks claims as **Verified** (direct source), **Reported** (credible third-party/review/user report), or **Inference** (our engineering conclusion). There is **no published deadline, required platform, team-size rule, or mandated technology** in the supplied Markdown; those must not be invented.

### Rubric-led positioning

| Rubric opportunity | Evidence to show in submission/demo | Target score logic |
|---|---|---|
| Expensive status quo | Screenshot/archive of Wispr Flow Pro at $15/month, Willow Pro at $15/month, and Superwhisper Pro at $8.49/month; cite live pages | Specific incumbents rather than “AI is expensive.” |
| Reach | Wispr is cross-platform and positioned as system-wide dictation; MacWhisper’s official Gumroad page displays 561,217 sales. Also distinguish this product signal from the much broader reach of Apple/Windows built-ins. | Use only supplied/product-page numbers; avoid claiming all users are paid dictation customers. |
| Coolness | Live global hotkey, local waveform/status, app-aware output, glossary correction, reversible transform | A build judges can operate beats mock screens. |
| Cost | Subscription comparator: $8.49–$15/user/month = $101.88–$180/year. OpenFlow local mode: $0 recurring software/API cost; user supplies existing computer/mic/electricity. | Be precise: “$0 recurring app/API cost,” not “zero total cost.” |
| Openness | Apache-2.0 code, third-party notices, model download checksums, build script and issue tracker | Apache-2.0 is permissive and business-friendly; MIT would also satisfy the rubric. |

---

## 2. Market landscape: what exists and what it proves

### Segment map

| Segment | Examples | Market lesson |
|---|---|---|
| AI system-wide dictation subscriptions | Wispr Flow, Willow, Aqua Voice, Superwhisper, Typeless | The desired UX is voice input directly into the app currently in focus, not a separate transcription editor. |
| Local/private desktop transcription | VoiceInk, MacWhisper, WhisperInk, Wspr | On-device processing is now a credible product expectation, though device performance varies. |
| Professional command-and-control | Dragon Professional | Custom vocabulary, AutoText and voice macros remain valuable beyond raw accuracy. |
| OS accessibility/dictation | Apple Dictation, Windows Voice Access | Free built-ins establish a baseline, but platform/language/hardware limits leave room for a cross-device local product. |
| Open-source building blocks/products | Whisper, faster-whisper, whisper.cpp, Silero VAD, Whisper Local, Vocalinux | The feature can be built legally and cheaply without reverse-engineering binaries or copying proprietary code. |

### Detailed competitor findings

#### Wispr Flow — strongest “frictionless writing anywhere” reference

**Verified:** Wispr Flow states that its macOS/Windows app works in any text field and names Notion, Gmail, Slack, Google Docs, Outlook, Linear, and Obsidian. Its public pricing page shows a free plan with a limit and a paid plan, while current official help documents list Pro at **$15/month or $144/year**; pricing pages may differ by region/version, so the live linked page must be rechecked on demo day. It advertises filler-word removal, AI cleanup/formatting, personal vocabulary, local processing mode, a shortcut, and cross-device use. Its Smart Formatting documentation describes lowercasing after an existing sentence, message-specific period removal, explicit new-line commands, and an undo of the AI edit. Its context documentation states that it excludes password fields and some financial apps, a useful safety pattern. [Pricing](https://wisprflow.ai/pricing) · [What Flow is](https://docs.wisprflow.ai/articles/2772472373-what-is-flow) · [Smart Formatting/Backtrack](https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-and-backtrack) · [Context safeguards](https://docs.wisprflow.ai/articles/4678293671-feature-context-awareness)

**UX lesson:** Make one gesture available everywhere; do not force a user into a document window. Use immediate, confidence-building feedback and a “backtrack” correction action.  
**Gap/opportunity:** English-only is stated on one current pricing page, and Windows has less context capability than macOS in its own context documentation. A Windows-first local glossary for multilingual/technical terms can be demonstrable differentiation.  
**Implementation inference:** Use a global hotkey, clipboard restore/paste transaction, Windows UI Automation only after explicit permission, and a deterministic safety allow/deny list. Do not assume Wispr’s ASR/LLM architecture is public.

#### Superwhisper — best mode/prompt composition reference

**Verified:** Superwhisper offers dictation in any app, 100+ languages, local Whisper models, custom prompt control, and a Free tier. Its public page lists Pro at **$8.49/month** and says Pro includes own API keys, cloud/local model access, translation to English, and audio/video transcription. Its public documentation repository shows custom modes that can select contexts such as selected text. [Product and pricing](https://superwhisper.com/) · [Custom-mode documentation](https://github.com/superultrainc/superwhisper-docs/blob/main/modes/custom.mdx)

**UX lesson:** Separate *intent* from transcription with clearly named modes (Dictate, Email, Code, Translate).  
**Reported limitation:** User discussion reports occasional over-eager custom prompting and issues around paragraphing; treat this as anecdotal, not a product fact. [Example user report](https://www.reddit.com/r/superwhisper/comments/1uuiqzv/mode_keeps_replying_to_my_prompt_instead_of_just/)

**Implementation inference:** Preset transformation templates should have constrained outputs (text-only; no assistant reply) and always preserve raw transcription so users can undo. For a hackathon, three audited presets beat arbitrary user-authored prompts.

#### Aqua Voice — strongest technical-speech/personalization reference

**Verified:** Aqua’s developer documentation describes its Avalon model, per-user dictionary, replacements, custom instructions, learned preferences, and a voice-editing operation that uses selected-text/app context. It exposes OpenAI-compatible transcription endpoints and lists API pricing of **$0.39/audio hour for transcription** and **$0.49/audio hour for dictation**. Its Android page states that audio/text are sent to its servers and that it supports many dictation languages. [API/platform documentation](https://aquavoice.com/api) · [Android product page](https://aquavoice.com/android)

**UX lesson:** A dictionary is not a settings afterthought; it belongs in the correction loop. Voice editing of selected text has a clear value proposition.  
**Gap/opportunity:** Cloud transfer and usage pricing offer a clean contrast for local-first use. Do not claim to match Avalon’s technical benchmark without measuring it ourselves.  
**Implementation inference:** Store replacements and canonical terms in an editable local SQLite/JSON glossary. Apply ASR prompt biasing where supported, then post-correct exact variants. Show each applied replacement.

#### Willow — writing-style memory and enterprise contrast

**Verified:** Willow’s page lists Basic free and Pro at **$15/month or $12/user/month annual**, with unlimited stronger transcription, smart memory of writing style, unlimited Scribe use, and longer dictation; Business adds zero-retention, SOC 2 Type II, HIPAA, administration, and shared dictionary features. It says it works anywhere a user can type and supports 100+ languages. [Pricing and plan features](https://willowvoice.com/pricing)

**UX lesson:** Users value a default that sounds like them, and teams value shared terminology.  
**Gap/opportunity:** “Memory” without inspectability is a trust problem. OpenFlow can make personalization legible: a local “terms I learned” list with edit/delete/export controls.  
**Implementation inference:** Do not implement enterprise compliance claims in a hackathon. Demonstrate local storage and transparent controls instead.

#### VoiceInk — local-first design and consent reference

**Verified:** VoiceInk describes local models and local processing on Apple Silicon. Its setup documentation is unusually useful: microphone permission is for recording; accessibility is for paste/keyboard/selected-text context; screen recording is for optional on-device screen context; it calls out hardware limits and makes AI enhancement optional. [Product page](https://tryvoiceink.com/) · [Permission/model setup](https://tryvoiceink.com/docs/installation)

**UX lesson:** Explain every permission in plain language at the moment it is requested. Make higher-risk context optional.  
**Gap/opportunity:** Its cited setup is macOS-centered. A transparent Windows implementation is directly relevant to the supplied development environment.  
**Implementation inference:** Build a permissions panel: microphone required; accessibility/input injection required for paste; app/selected-text context optional; never capture secure fields.

#### MacWhisper — local performance and export/integration reference

**Verified:** MacWhisper’s official listing says transcription is performed on-device, supports system-wide dictation, filler removal, 100 languages, model choices, meeting recording, export formats, editing, and GPU acceleration. Its listing displays **561,217 sales** and a one-time paid Pro tier; price is region/currency dependent. It also documents newer speaker recognition, real-time meetings, and Qwen3-ASR support. [Feature list and sales count](https://goodsnooze.gumroad.com/l/macwhisper) · [Pro feature list](https://goodsnooze.gumroad.com/l/macwhisper?featured_on=talkpython) · [15.2 update](https://goodsnooze.gumroad.com/p/macwhisper-15-2-improved-speaker-recognition-realtime-meetings-apple-intelligence-and-new-qwen-model)

**UX lesson:** Let users choose speed/accuracy and retain an editable transcript.  
**Gap/opportunity:** It is Mac-focused and feature-rich beyond a hackathon’s scope. Avoid building meetings, diarization, exports, and integrations before dictation is excellent.  
**Implementation inference:** Provide a “fast / accurate” model choice only if model download/latency are dependable; otherwise fix one model for the demo.

#### Dragon Professional — the command/control benchmark

**Verified:** Nuance says Dragon Professional supports live and recorded-audio transcription, custom voice commands, boilerplate insertion, automation macros, custom vocabularies, and administrative sharing. It markets up to 99% recognition and 3x typing speed; these are vendor claims, not independently replicated metrics. [Dragon Professional](https://dragon.nuance.com/en-us/dragon-professional) · [Feature matrix](https://dragon.nuance.com/asset/en_us/collateral/dragon/feature-matrix/fm-dragon-professional-v16-and-dragon-professional-anywhere-comparison-en-us.pdf)

**UX lesson:** The lasting differentiator is not transcribing words; it is transforming voice into repeatable workflows.  
**Gap/opportunity:** A safe micro-version is enough: local spoken snippets (e.g., “insert stand-up template”) and simple text navigation, not arbitrary OS automation.  
**Implementation inference:** Never run arbitrary shell commands from speech in the MVP. Offer snippet insertion only, showing exactly what will be inserted.

#### Built-ins: Apple Dictation and Windows Voice Access

**Verified:** Apple documents that iPhone Dictation can work in many languages without internet and, on stated hardware/software, uses an on-device model to improve spelling, punctuation, and capitalization. Microsoft documents that Voice Access on Windows 11 lets users control the PC and author text with voice without internet; Windows Speech Recognition was replaced by Voice Access for newer Windows 11. [Apple Dictation](https://support.apple.com/guide/iphone/dictate-text-iph2c0651d2/27/ios/27) · [Microsoft Voice Access](https://support.microsoft.com/en-us/accessibility/windows/voice-access/use-voice-access-to-control-your-pc-author-text-with-your-voice)

**UX lesson:** Free OS dictation is the baseline, not the enemy. OpenFlow must explain why it is better: a global hold-to-talk workflow, inspectable personalization, local glossary, and writing modes.  
**Constraint:** Windows Voice Access may overlap with microphone/hotkey behavior. During a demo, disable competing dictation tools.

#### Typeless and emerging local/open alternatives

**Verified:** Typeless says it dictates in any text field across apps/websites; its setup guide positions Dictate and Translate as clear-writing modes. [Typeless setup](https://www.typeless.com/help/installation-and-setup)  
**Verified:** Whisper Local is a public open-source project that advertises fully offline push-to-talk, transforms, voice commands, and faster-whisper; Vocalinux describes fully offline Linux dictation with several local engines. They are valuable references/possible ideas, not code to copy without their licence/attribution review. [Whisper Local](https://github.com/drajb/whisper-local) · [Vocalinux](https://github.com/VocaHQ/vocalinux)

**Market takeaway:** The open-source gap is not “local transcription exists.” The opportunity is a polished, trustworthy, Windows-first product that makes local processing, corrections, and context boundaries obvious.

---

## 3. Cross-application feature comparison and build decision matrix

Ratings are planning estimates for a two-to-four person hackathon team: **S** ≤4 focused hours, **M** 0.5–1 day, **L** 1–2 days, **XL** 3+ days. “Rubric value” identifies the criterion most directly strengthened.

| Feature | Existing examples and user-facing behavior | Why it matters | OpenFlow implementation path | Difficulty/dependencies | User impact | Rubric value |
|---|---|---|---|---|---|---|
| Global push-to-talk, output in focused app | Wispr, Superwhisper, VoiceInk, MacWhisper all position dictation as available across apps | Removes workflow switching; enables a live wow moment | Global hotkey → record → transcribe → clipboard transaction → restore clipboard → paste | **M**; OS input APIs, microphone, clipboard | Very high | Coolness |
| Local ASR with visible privacy state | VoiceInk/MacWhisper; Whisper Local | Makes $0 recurring and privacy claims credible | Bundle/download Whisper model; show “On-device / no network” indicator | **M**; model/runtime/packaging | Very high | Cost reduction, coolness |
| Filler removal/punctuation | Wispr, Willow, MacWhisper, Apple | Turns speech into usable prose | Deterministic filler filter + ASR punctuation; preserve raw text | **S** | High | Coolness |
| App-aware formatting | Wispr recognizes messages/email/code comments | Reduces rewrite friction | Detect active process/window category; three transparent style presets | **M** without reading text; **L** with UIA context | High | Coolness |
| Writing modes/custom prompts | Superwhisper modes; VoiceInk optional enhancement | Same speech can become an email, note, prompt, or code comment | Start with Dictate, Professional Email, Developer; raw/processed toggle | **M**; local LLM optional | High | Coolness |
| Personal glossary/replacements | Wispr personal vocabulary; Aqua dictionary; Dragon vocabulary | Prevents embarrassing names/acronym errors | Local term list plus “learn this correction” action; ASR initial prompt/replacement map | **S–M** | Very high | Coolness, reach |
| Reversible correction/backtrack | Wispr undo AI edit | Trust requires recovery from bad cleanup | Floating preview contains Copy, Paste, Raw, Undo; persist no audio by default | **S** | High | Coolness |
| Voice edit selected text | Aqua edit; Dragon command/editing | Lets users repair prose without hands | Selected text → local transform; only after explicit permission | **L**; UIA/clipboard | Medium-high | Coolness |
| Snippet/AutoText commands | Dragon commands | Converts dictation into productivity automation | Safe local phrase→text snippets; no arbitrary system execution | **S** | Medium | Coolness |
| Multilingual auto-detect/translation | Superwhisper, Willow, MacWhisper | Important for diverse users and SEA use cases | Whisper multilingual model; display detected language; defer translation | **M** | Medium | Reach |
| Live partial transcript | Microsoft Voice Access, MacWhisper meetings | Reassures users during longer speech | Chunked ASR/streaming; hard to perfect | **L–XL** | Medium | Coolness |
| Voice activity detection / auto-stop | Whisper Local, Vocalinux | Natural hands-free stop and shorter latency | Silero VAD end-of-speech with manual PTT fallback | **M** | Medium | Coolness |
| Context reading with exclusions | Wispr, VoiceInk | Better capitalization, tone, and selected-text edits | Opt-in UI Automation; field/process allowlist, never passwords/financial apps | **L**; privacy engineering | High if reliable | Coolness, openness |
| Team/shared dictionary | Willow, Dragon | Valuable to teams, not necessary to prove core value | Post-hack encrypted/shared sync | **L** | Medium | Reach |
| Meeting capture/diarization/export | MacWhisper | Valuable adjacent market, distracts from dictation | Explicitly defer | **XL** | Low for target demo | Low |
| Full OS control via voice | Dragon, Windows Voice Access | Accessibility value but high safety/UX burden | Do not build for MVP | **XL** | Potentially high, high risk | Low |

### The 12 strongest ideas to carry forward

1. Hold-to-talk, type-anywhere insertion.
2. Local ASR with a prominent privacy/cost indicator.
3. Filler removal, punctuation, capitalization, and paragraphing.
4. Reversible raw-versus-clean output.
5. Local correction-learning glossary.
6. Context *category* modes: chat, email, developer—not invisible broad screen scraping.
7. Selected-text voice rewrite (only if permission/user selection works).
8. Safe spoken snippets/AutoText.
9. Multilingual recognition with a model/language control.
10. VAD-assisted hands-free auto-stop alongside reliable push-to-talk.
11. Inspectable per-app rules and a sensitive-app exclusion list.
12. Fast/accurate model selection with clear download size/latency trade-off.

---

## 4. Legitimate feature adaptation: what to reproduce, not proprietary internals

| Candidate | Public behavior worth emulating | Best source example | Lawful adaptation | Main technical/product risk |
|---|---|---|---|---|
| “Speak naturally; it lands where I am” | Global trigger and focused-field delivery | Wispr / Superwhisper | Implement standard OS hotkey, capture and paste facilities; do not inspect/copy binaries | Focus can change while ASR runs; capture target window/process at start and warn if it changed. |
| Context-sensitive writing | Chat text is short/casual; email is polished; code has code conventions | Wispr formatting docs | Map *active app category* to an inspectable template; optionally read a limited selected-text window | Hidden context capture can expose secrets; require opt-in and exclusions. |
| AI cleanup | Remove disfluencies and resolve self-corrections | Wispr/Willow/Eloquent reports | Deterministic cleanup first; optional local LLM with strict output contract | LLM may alter factual meaning; raw text and undo must always exist. |
| Vocabulary learning | Correct names/terms become durable | Aqua/Dragon/Wispr | User approves `heard → intended` pair, stored locally/exportable | Blind auto-learning can fossilize an error; require confirmation. |
| Voice editing | Speak instruction over selected text | Aqua | Explicit selection + command grammar: “make concise,” “make professional,” “turn into bullets” | UI Automation/clipboard is fragile; demo it in one known app. |
| Repeated text/macro | Spoken phrase inserts a template | Dragon | Allow only static local snippets and visible preview | Never interpret voice as executable shell/PowerShell; this is a security boundary. |

### Useful open-source accelerators and licence notes

| Component | Verified role | Licence/status | Recommendation |
|---|---|---|---|
| [OpenAI Whisper](https://github.com/openai/whisper) | Multilingual ASR model/reference implementation | MIT repository licence; model use must be reviewed at release | Viable model baseline. |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Python Whisper implementation on CTranslate2, quantization | MIT; project claims up to 4× speed/memory improvements versus reference under its benchmarks | Fastest route for Python prototype; GPU dependency packaging can be difficult. |
| [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | C/C++ local inference with streaming examples and Windows/CUDA/Vulkan options | MIT | Stronger packaged Windows desktop route; has `whisper-stream`/command examples. |
| [Silero VAD](https://github.com/snakers4/silero-vad) | End-of-speech detection | MIT | Add only after PTT works. |
| [Whisper Local](https://github.com/drajb/whisper-local) / [Vocalinux](https://github.com/VocaHQ/vocalinux) | Public product-pattern references | Verify their licences before using code | Study design/testing ideas; do not copy code unless licence compatibility and attribution are confirmed. |

**Licence discipline:** Apache-2.0 for the application is recommended because it is clear and permissive, including a patent grant. Include `NOTICE`/third-party licence files. Apache-2.0 code can include MIT components with notices. Do not describe a model as “open source” merely because a runner is MIT; model-weight terms must be verified separately at the selected model’s source before release.

---

## 5. Gaps worth solving and a defensible differentiator

### What competitors already do very well

- System-wide dictation and polished cleanup are mature in Wispr Flow, Willow, Superwhisper, and Aqua.
- Apple and Windows offer free baseline authoring/accessibility features.
- MacWhisper and VoiceInk make local transcription credible for capable hardware.
- Dragon remains unusually strong in customizable vocabulary/commands.

### Recurrent gaps

| Gap | Why it persists | Product response |
|---|---|---|
| Local processing is often a setting, not a trustworthy story | Users cannot tell whether a mode/model sent data or saved audio | A permanent local-only indicator, network-disabled test, transparent local data folder, and no account. |
| “AI cleanup” can silently change meaning | Generative transformations are opaque | Raw text, highlighted edits, copy raw, and one-click undo. Default to conservative transformations. |
| Personalization is invisible/vendor-owned | Memory is an opaque cloud benefit | A user-owned local glossary and edit log: “We changed `N U S` to `NUS` because you approved it.” |
| Context awareness trades quality for privacy | Reading screens/selections risks sensitive data | Context by app category first; optional selected text; explicit red-zone app/field exclusions. |
| Powerful voice commands can be unsafe | Natural language command execution can trigger harmful actions | Static snippets only in MVP; no arbitrary code, browser action, or shell execution. |
| Windows local-first polish is thinner than Mac offerings | Many polished local apps target macOS/Apple Silicon | Make Windows the primary demo platform, with a portable architecture. |

### Recommended differentiator: **Proof-of-Local + Explainable Personalization**

The feature is not a gimmick. It solves the real adoption barrier: people hesitate to dictate private work and abandon ASR after name/jargon errors.

**User-visible behavior:** after dictating “email Professor Sze about the MERaLiON workshop,” the app produces the correct terms from a local glossary. If it gets a term wrong, the user corrects it once and sees an editable rule. The activity panel shows `On device • Whisper model • Network requests: 0 • audio discarded after transcription`. The user can open/export/delete all learned data.

**Why it can win:** It combines a paid-product strength (personal vocabulary) with a defensible open-source/local property, and gives judges something concrete to inspect. It is better than claiming generic “privacy” without proof.

---

## 6. Prioritized scope against the actual rubric

### Must-have MVP (build in this order)

| Feature | Value / feasibility | Estimated effort | Demo impact | Rubric alignment | Decision |
|---|---|---:|---|---|---|
| Global PTT → local transcript → paste into Notepad/Slack-like web field | Core interaction; technically bounded | M | Essential | Coolness 25% | **Must-have** |
| On-device status and $0 recurring-cost screen | Low complexity, makes claim auditable | S | Very high | Cost reduction 25%, openness 15% | **Must-have** |
| Conservative cleanup (fillers, spacing, punctuation) with Raw/Undo | High value, avoids unsafe LLM dependency | S–M | High | Coolness | **Must-have** |
| Local personal glossary + correction confirmation | Strong differentiation, reliable demo | S–M | Very high | Coolness, reach | **Must-have** |
| Public repo, Apache-2.0 `LICENSE`, notices, install/demo instructions | Required proof, not polish | S | Essential | Open source 15% | **Must-have** |

### High-impact additions

| Feature | Trade-off | Estimated effort | Decision |
|---|---|---:|---|
| Three transparent style modes (Chat / Email / Developer) | Better demo; needs constrained local rules/LLM | M | **Build after must-haves** |
| Active-app category formatting | Useful without content inspection | M | **Build** |
| Voice rewrite of selected text | Striking if browser/Word selection works; permission fragile | L | **Attempt if integration is stable** |
| Safe AutoText snippets | Shows Dragon-inspired productivity without security risk | S | **Build if time permits** |
| VAD auto-stop | Polished hands-free feel; PTT remains fallback | M | **Build only after PTT** |

### Stretch goals

- Live partial text while speaking (hard latency/duplication problems).
- Optional local LLM rewrite with an explicit model download and raw-text diff.
- Multilingual automatic language detection and translation.
- Local selected-text/app context via Windows UI Automation with sensitive-app exclusions.
- Benchmarked accuracy/latency dashboard across models.

### Post-hackathon, not suitable for first build

- Meeting capture, system-audio capture, speaker diarization, transcript library and exports.
- Team sync/shared dictionary, SSO/compliance claims, cloud sync.
- General OS automation or free-form agent actions from voice.
- Mobile apps and cross-device syncing.

### Trade-off that should be explicit

Do **not** sacrifice a reliable offline PTT/paste loop for an ambitious LLM agent. Under this rubric, an impressive working local build with a measured $0 recurring cost is worth more than a broad, brittle feature checklist. An optional LLM must never block the core product.

---

## 7. Unified product experience

### Primary user

The primary hackathon user is a Windows student, developer, researcher, or knowledge worker who writes across chat, email, docs, terminals, and AI tools; has recurring names/technical terms; wants speed but does not want another transcription subscription or to send sensitive voice data to a cloud service. The project should not claim to replace specialized accessibility/medical dictation products without evaluation.

### End-to-end experience

1. **First run:** OpenFlow explains exactly three permissions: microphone; global hotkey/paste; optional context. It downloads a clearly labelled local model and lets the user add 3–5 glossary terms.
2. **Dictate:** The user focuses any ordinary editable field and holds `Ctrl+Space` (example; choose a conflict-free configurable shortcut). A small floating pill shows recording and on-device processing state.
3. **Review:** On release, the app emits raw transcript and conservative clean text. A tiny preview shows **Paste**, **Raw**, **Undo**, and **Learn correction**.
4. **Adapt:** A detected application category selects a visible mode: Chat avoids a formal sign-off, Email produces paragraphs, Developer preserves code tokens/glossary terms. Mode is displayed, not guessed invisibly.
5. **Trust:** The history is off by default or text-only local and erasable. The user can inspect the dictionary, delete all local data, and see whether any optional model was used.

### Product principles

- **Local is default, not a premium toggle.**
- **Every AI change is reversible.**
- **User controls are inspectable and exportable.**
- **No silent capture of selected text/screen.**
- **The default works in seconds, not after prompt engineering.**

---

## 8. Suggested technical architecture (proposal, not existing code)

### Recommended hackathon architecture: native Windows desktop shell + local engine

| Layer | Proposed choice | Why | Alternatives/notes |
|---|---|---|---|
| Desktop shell | Tauri 2 + Rust + small web UI | Small distributable, native tray/global-shortcut capabilities, public source | Python/PySide can be faster for a prototype; choose it if team fluency outweighs packaging polish. |
| Audio capture | Rust `cpal` or Python `sounddevice` | Direct mic stream | Buffer 16 kHz mono PCM locally; never upload in local mode. |
| End-of-turn | Push-to-talk first; Silero VAD second | PTT is deterministic; VAD adds polish later | Tune threshold with room-noise samples. |
| ASR | `whisper.cpp` with a quantized Whisper model | MIT, C/C++, CPU/CUDA/Vulkan options, streaming examples | `faster-whisper` is excellent for a Python MVP but GPU distribution requires care. |
| Cleanup | Deterministic pipeline: filler policy, whitespace, capitalization, glossary replacement | Stable, explainable, no LLM dependency | Optional Ollama/local LLM only behind a toggle, raw/processed diff. |
| Context | Active-window executable/title → category mapping | Delivers 80% of value without reading content | Opt-in Windows UI Automation for selected text only; do not screenshot by default. |
| Delivery | Preserve clipboard → write text → simulated `Ctrl+V` → restore clipboard after paste | More universal than direct field APIs | Capture focused window at recording start; if it changes, show a notification rather than paste somewhere unsafe. |
| Local state | SQLite or JSON in app data | Glossary, snippets, preferences, optional text history | No audio persistence by default; encrypting at rest is a post-hack improvement. |

### Data flow and trust boundaries

```text
Microphone
  → local PCM buffer
  → (optional local VAD)
  → local Whisper runtime
  → raw transcript (memory)
  → deterministic cleanup + local glossary
  → [optional, opt-in local LLM transform]
  → visible preview / raw-undo decision
  → clipboard transaction → focused application

Local-only boundary: no audio/text network request in default mode.
Optional context boundary: active-app category only by default; selected text requires explicit enablement.
```

### Security and privacy requirements for the MVP

- Do not paste into password/PIN fields; disable capture/delivery for known credential/financial apps when detectable.
- Never execute dictated text as a command. Pasting into a terminal is user-controlled and should display a warning/preview.
- Do not retain audio by default. Explain any text history setting and include a Delete All action.
- Do not claim HIPAA/SOC 2/GDPR compliance based merely on local processing.
- Pin model/runtime downloads with version/checksum, document licences, and let users inspect the model source.
- Test the clipboard restore flow with Unicode text and failure cases; never silently destroy a user’s copied content.

### Performance acceptance criteria to measure, not promise

Before the demo, record a small reproducible evaluation set (with consent) containing casual speech, technical terms, and a quiet/noisy room sample. Report:

| Metric | Target for a hackathon demo | Measurement |
|---|---|---|
| Hotkey-to-record feedback | <150 ms perceptual response | timestamp/UI log |
| End-of-speech to paste-ready preview | <2 seconds for a 5–10 second utterance on demo laptop | median of 10 runs |
| Glossary accuracy | 100% for a fixed demo glossary | 10 repeated terms |
| Clipboard preservation | 10/10 test cases | pre/post clipboard test |
| Network use in local mode | 0 requests | firewall/devtools/OS monitor screenshot |

Do not advertise generic “99% accuracy” or “real-time” unless these measures are actually run and retained.

---

## 9. Demo, submission, and evidence plan

### 90-second live demo

1. **Cost setup (10 s):** show three subscription screenshots: Wispr $15/month, Willow $15/month, Superwhisper $8.49/month. State $101.88–$180/year versus OpenFlow’s $0 recurring software/API cost.
2. **Core magic (20 s):** focus an email field; hold the hotkey; say a natural, disfluent sentence containing “NUS,” “MERaLiON,” and a project-specific acronym; release; polished text appears and pastes.
3. **Same speech, different surface (20 s):** dictate a project update into a Slack-like field and show a concise no-period chat version; then use Developer mode for a code-comment/terminal *preview*. Avoid executing a command.
4. **Correction/trust (20 s):** intentionally make/seed one incorrect jargon result, correct it with Learn correction, repeat; show glossary and local-only status (`Network requests: 0`).
5. **Open proof (20 s):** show public repository, Apache-2.0 licence, third-party notices and architecture; give judges the hotkey to try.

### Submission checklist

- [ ] Public repository URL on the README and a visible `LICENSE` (Apache-2.0 recommended).
- [ ] Direct citations/pricing snapshot date in README or pitch deck.
- [ ] Reproducible Windows build/run instructions and model download size/hardware notes.
- [ ] Third-party notices and model-weight licence review.
- [ ] No API key required for core local demo.
- [ ] 1-minute backup video of the exact demo in case of permissions/model cold-start failure.
- [ ] Local/offline verification artifact and latency test table.
- [ ] Clear statement of what is implemented versus roadmap.

---

## 10. Research limits and validation tasks

- Product prices, feature tiers and supported platforms are mutable. Reopen official pages immediately before submission and date screenshots.
- Vendor claims such as Dragon’s speed/accuracy are vendor marketing, not comparative benchmarks.
- “Reach” is the weakest evidence category for niche paid dictation. MacWhisper’s displayed sales count is a concrete signal; do not extrapolate it to market share. If time permits, find an official Wispr/Willow download/user statistic or phrase the reach claim as broad OS-addressable reach rather than paid-customer count.
- Public documentation reveals product behavior, not proprietary models, prompts, training data, or server architecture. Those are intentionally not inferred as fact.
- Test actual active-window/context behavior on the intended Windows version. UI Automation, clipboard handling, permissions, antivirus and global shortcuts are integration risks, not solved by research.

---

## Sources and references

### Competition/project sources

- [Autonomous SG 2026 / NUS Hackers official problem statement and rubric](Autonomous%20SG%202026_NUS_Hackers.md)
- [Repository source-note inventory: Full-Stack AI Engineering Course transcript](youtube-XzjSx7u9mGw.md)

### Primary product and platform sources

- [Wispr Flow pricing](https://wisprflow.ai/pricing)
- [Wispr Flow: what it is](https://docs.wisprflow.ai/articles/2772472373-what-is-flow)
- [Wispr Smart Formatting and Backtrack](https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-and-backtrack)
- [Wispr context awareness safeguards](https://docs.wisprflow.ai/articles/4678293671-feature-context-awareness)
- [Superwhisper product/pricing](https://superwhisper.com/)
- [Superwhisper custom modes documentation](https://github.com/superultrainc/superwhisper-docs/blob/main/modes/custom.mdx)
- [Aqua Voice API, personalization, editing, and usage pricing](https://aquavoice.com/api)
- [Aqua Voice Android privacy/language statement](https://aquavoice.com/android)
- [Willow pricing and feature comparison](https://willowvoice.com/pricing)
- [VoiceInk product page](https://tryvoiceink.com/)
- [VoiceInk model/permission documentation](https://tryvoiceink.com/docs/installation)
- [MacWhisper official feature list and sales count](https://goodsnooze.gumroad.com/l/macwhisper)
- [MacWhisper Pro features](https://goodsnooze.gumroad.com/l/macwhisper?featured_on=talkpython)
- [Dragon Professional product page](https://dragon.nuance.com/en-us/dragon-professional)
- [Dragon Professional feature matrix](https://dragon.nuance.com/asset/en_us/collateral/dragon/feature-matrix/fm-dragon-professional-v16-and-dragon-professional-anywhere-comparison-en-us.pdf)
- [Apple Dictation support](https://support.apple.com/guide/iphone/dictate-text-iph2c0651d2/27/ios/27)
- [Microsoft Voice Access support](https://support.microsoft.com/en-us/accessibility/windows/voice-access/use-voice-access-to-control-your-pc-author-text-with-your-voice)
- [Typeless installation and setup](https://www.typeless.com/help/installation-and-setup)

### Open-source and technical sources

- [OpenAI Whisper](https://github.com/openai/whisper)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp)
- [Silero VAD](https://github.com/snakers4/silero-vad)
- [Whisper Local](https://github.com/drajb/whisper-local)
- [Vocalinux](https://github.com/VocaHQ/vocalinux)

### Secondary/reported context (not used as proof of proprietary implementation)

- [Google AI Edge Eloquent report and feature overview](https://www.tomsguide.com/ai/google-just-launched-a-free-ai-dictation-app-that-fixes-your-speech-and-it-even-works-offline)
- [Superwhisper user report on custom-mode output behavior](https://www.reddit.com/r/superwhisper/comments/1uuiqzv/mode_keeps_replying_to_my_prompt_instead_of_just/)

