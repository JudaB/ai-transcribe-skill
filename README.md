# ai-transcribe-skill

A [Claude](https://claude.com/claude-code) **skill** that transcribes a local
audio file to text using the [Soniox](https://soniox.com) async speech-to-text
API — with speaker diarization and Hebrew/English language identification.

It wraps a small, dependency-free Python script (standard library only) that
handles the full Soniox flow: upload → poll → fetch → clean up.

## Install (Claude Code plugin)

This repo is a self-hosted Claude Code **marketplace** containing one plugin,
`transcribe-audio`. From an interactive `claude` terminal:

```bash
/plugin marketplace add JudaB/ai-transcribe-skill
```
```bash
/plugin install transcribe-audio@ai-transcribe-skill
```

Then just ask Claude to transcribe a local audio file.

**Or install as a plain skill** (no marketplace) by cloning the skill folder
directly:

```bash
git clone https://github.com/JudaB/ai-transcribe-skill.git /tmp/ai-transcribe-skill
cp -r /tmp/ai-transcribe-skill/skills/transcribe-audio ~/.claude/skills/transcribe-audio
```

Either way, provide a Soniox API key (see [Setup](#setup)).

## What it produces

For an input like `lesson.mp3`, it writes three files next to the audio:

| File | Contents |
| --- | --- |
| `lesson-soniox.json` | Full Soniox result — tokens with per-token speaker, language, and timestamps |
| `lesson.txt` | Flat running transcript |
| `lesson-speakers.txt` | Speaker-labeled transcript (`Speaker 1: …`, `Speaker 2: …`) |

## Requirements

- **Python 3.8+** (no `pip install` — standard library only)
- A **Soniox API key** — get one at <https://console.soniox.com> → API Keys

## Setup

Provide your Soniox API key in any one of these ways (checked in this order):

1. `SONIOX_API_KEY` environment variable
2. `--key <KEY>` argument
3. A key file at `~/.claude/skills/transcribe-audio/soniox.key` or `~/.soniox.key`

> **Never commit your key.** This repo's `.gitignore` excludes `*.key`, but keep
> your key out of the repo regardless.

## Usage as a standalone script

```bash
python skills/transcribe-audio/scripts/transcribe.py "path/to/audio.mp3"
```

### Options

| Option | Description |
| --- | --- |
| `--provider soniox` | Clean transcript, filler words removed **(default)** |
| `--provider soniox-disfluencies` | Verbatim — keeps filler words / hesitations (אממ, אהה, um, uh) |
| `--outdir <dir>` | Write outputs somewhere other than next to the audio |
| `--language-hints he,en` | Language hints (default `he,en`) |
| `--model <id>` | Soniox model (default `stt-async-v5`) |
| `--key <KEY>` / `--key-file <path>` | Provide the API key inline or from a file |
| `--keep-remote` | Don't delete the uploaded file/job from your Soniox account |

Long files take a few minutes; the script polls Soniox and logs status to stderr,
then prints a small JSON summary (detected language + output paths) on stdout.

## Usage as a Claude skill

Once installed (see [Install](#install-claude-code-plugin)), just ask Claude to
transcribe any local audio file — e.g. "transcribe this mp3" — and it will run
the script, poll to completion, and report the output files.

## Notes

- The script uploads the file directly to Soniox, so no public URL is needed.
- Speaker labels are Soniox's diarization guesses — they distinguish *distinct*
  speakers, not *who* they are.
- By default the uploaded file and job are deleted from your Soniox account after
  a successful run (pass `--keep-remote` to keep them).

## License

See [LICENSE](LICENSE).
