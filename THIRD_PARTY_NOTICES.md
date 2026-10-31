# Third-party notices

Utter is distributed under Apache-2.0. It does not include third-party source code. It installs and uses
the following components, each under its own licence. Versions are pinned in `utter/pyproject.toml`.

## Direct dependencies

| Component | Used for | Licence |
|---|---|---|
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 1.2.1 | Local Whisper inference | MIT |
| [CTranslate2](https://github.com/OpenNMT/CTranslate2) 4.8.4 | Inference engine under faster-whisper | MIT |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) 0.5.6 (+ bundled PortAudio) | Microphone capture | MIT (PortAudio: MIT-style) |
| [keyboard](https://github.com/boppreh/keyboard) 0.13.5 | Global hotkey and simulated paste | MIT |
| [pyperclip](https://github.com/asweigart/pyperclip) 1.11.0 | Clipboard access | BSD-3-Clause |
| [NumPy](https://numpy.org) | Audio buffers | BSD-3-Clause |
| [Pydantic](https://github.com/pydantic/pydantic) 2.14.2 | Validating config and results | MIT |

## Pulled in by faster-whisper

| Component | Licence | Note |
|---|---|---|
| [onnxruntime](https://github.com/microsoft/onnxruntime) | MIT | Runs the bundled Silero VAD model |
| [Silero VAD](https://github.com/snakers4/silero-vad) (bundled in faster-whisper) | MIT | Voice-activity detection |
| [huggingface_hub](https://github.com/huggingface/huggingface_hub), [tokenizers](https://github.com/huggingface/tokenizers) | Apache-2.0 | Model download (first run only) and tokenisation |
| [PyAV](https://github.com/PyAV-Org/PyAV) | BSD-3-Clause | Its wheels bundle FFmpeg libraries under LGPL-2.1+. Utter passes raw audio arrays and never calls FFmpeg for decoding. |

## Model weights

| Model | Source | Licence |
|---|---|---|
| Whisper `base.en` / `small.en` (CTranslate2 conversion) | [Systran/faster-whisper-base.en](https://huggingface.co/Systran/faster-whisper-base.en), [Systran/faster-whisper-small.en](https://huggingface.co/Systran/faster-whisper-small.en), converted from [OpenAI Whisper](https://github.com/openai/whisper) | MIT |

Models are downloaded once by `python -m utter download-model` into `%LOCALAPPDATA%\Utter\models`.
They are not committed to this repository.

## Development only
pytest (MIT), ruff (MIT), mypy (MIT).
