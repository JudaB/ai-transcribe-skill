---
name: transcribe-audio
description: "Transcribe a local audio file (mp3/wav/m4a) to text using the Soniox async speech-to-text API, with speaker diarization and Hebrew/English language identification. Use this whenever the user wants to transcribe, get a transcript of, write out, or convert to text any audio or voice recording, lecture, lesson, meeting, interview, or call (including Hebrew audio) even if they don't say the word Soniox. Also use it when they point at an .mp3/.wav/.m4a file and ask what's said in it or want speaker-labeled text."
---

# Transcribe audio (Soniox)

Turn a local audio file into text. The heavy lifting is done by a bundled,
dependency-free script that talks to the Soniox async API; your job is to gather
the inputs, run it, and present the result.

## Prerequisites

A **Soniox API key** must be available. The script looks for it in this order:

1. `$SONIOX_API_KEY` environment variable
2. `--key` argument
3. a key file: `~/.claude/skills/transcribe-audio/soniox.key` or `~/.soniox.key`

If none is set, the script exits with instructions. If you hit that, ask the user
for their key (from `https://console.soniox.com` → API Keys) and offer to save it
to `~/.claude/skills/transcribe-audio/soniox.key` for next time. Never print the
key back to the user or commit it anywhere.

Python 3.8+ is required (standard library only — no `pip install` needed).

## Steps

1. **Confirm the audio path.** Get the absolute path to the file. If the user
   referenced a file loosely ("that mp3 from lesson 3"), resolve it to a concrete
   path first and confirm.
2. **Run the script:**

   ```bash
   python "<skill-dir>/scripts/transcribe.py" "<audio-file>"
   ```

   Long files take minutes — the script polls Soniox and logs status to stderr.
   Because it can be slow, prefer running it as a background command and reporting
   when it finishes, rather than blocking.
3. **Report the outputs.** On success the script prints a JSON summary on stdout
   (detected language + output paths) and writes three files next to the audio
   (or into `--outdir`):
   - `<name>-soniox.json` — the full Soniox result (tokens with per-token speaker,
     language, and timestamps). This is the "conversation JSON".
   - `<name>.txt` — flat running transcript.
   - `<name>-speakers.txt` — speaker-labeled transcript (`Speaker 1: …`).

   Link the files for the user and, if short, show a snippet of the speaker text.

## Options (pass through when the user asks)

- `--provider soniox-disfluencies` — verbatim: keeps filler words / hesitations /
  stutters (אממ, אהה, um, uh), useful for close analysis of *how* something was
  said. The **default is `soniox`** (clean transcript, filler words removed) —
  this is the recommended default; only pass `soniox-disfluencies` if the user
  explicitly asks for a verbatim / word-for-word transcript.
- `--outdir <dir>` — write outputs somewhere other than next to the audio.
- `--language-hints he,en` — adjust if the audio isn't Hebrew/English.
- `--model <id>` — defaults to `stt-async-v5`.
- `--keep-remote` — don't delete the uploaded file/job from the Soniox account
  (by default they're cleaned up after a successful run).

## Notes

- The script uploads the file to Soniox (their file endpoint), so no public URL is
  needed — local files work directly.
- Speaker labels are Soniox's diarization guesses (`Speaker 1`, `Speaker 2`, …);
  they identify *distinct* speakers, not *who* they are.
