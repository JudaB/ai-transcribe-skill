#!/usr/bin/env python3
"""Transcribe a local audio file with Soniox (async API) — speaker diarization,
he/en language ID, optional verbatim/disfluency mode. Zero third-party deps
(urllib only), so it runs anywhere Python 3.8+ is installed.

Outputs (written next to the audio file unless --outdir is given):
  <name>-soniox.json   full Soniox transcript result (tokens, languages, ...)
  <name>.txt           flat transcript (plain running text)
  <name>-speakers.txt  speaker-labeled transcript (Speaker 1: ... / Speaker 2: ...)

API key resolution order: --key, $SONIOX_API_KEY, then a key file
(--key-file, else ~/.claude/skills/transcribe-audio/soniox.key, else ~/.soniox.key).
"""

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

API = "https://api.soniox.com"

# Steer Soniox to keep filler words / hesitations / stutters verbatim. Soniox has
# no dedicated disfluency flag, so we ask for it via the free-text context field.
DISFLUENCY_CONTEXT = (
    "תמלל מילה במילה (verbatim). כלול את כל מילות המילוי, ההיסוסים, הגמגומים והחזרות "
    "(לדוגמה: אה, אממ, eh, um, uh). אל תנקה ואל תשמיט disfluencies."
)


def _force_utf8_streams():
    # On Windows the console defaults to a legacy code page (cp1252), so printing
    # Hebrew paths/text to stdout/stderr raises UnicodeEncodeError. Force UTF-8.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass  # older Python or already-wrapped stream


_force_utf8_streams()


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def resolve_key(args):
    if args.key:
        return args.key.strip()
    env = os.environ.get("SONIOX_API_KEY")
    if env and env.strip():
        return env.strip()
    candidates = []
    if args.key_file:
        candidates.append(args.key_file)
    home = os.path.expanduser("~")
    candidates.append(os.path.join(home, ".claude", "skills", "transcribe-audio", "soniox.key"))
    candidates.append(os.path.join(home, ".soniox.key"))
    for c in candidates:
        if c and os.path.isfile(c):
            with open(c, "r", encoding="utf-8") as f:
                k = f.read().strip()
            if k:
                return k
    sys.exit(
        "No Soniox API key found. Set $SONIOX_API_KEY, pass --key, or create a key "
        "file at ~/.claude/skills/transcribe-audio/soniox.key (get a key at "
        "https://console.soniox.com -> API Keys)."
    )


def api(method, path, key, body=None, multipart=None):
    url = API + path
    headers = {"Authorization": "Bearer " + key}
    data = None
    if multipart is not None:
        fpath = multipart
        boundary = "----soniox" + uuid.uuid4().hex
        fname = os.path.basename(fpath)
        ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
        with open(fpath, "rb") as f:
            file_bytes = f.read()
        pre = (
            "--%s\r\n"
            'Content-Disposition: form-data; name="file"; filename="%s"\r\n'
            "Content-Type: %s\r\n\r\n" % (boundary, fname, ctype)
        ).encode("utf-8")
        post = ("\r\n--%s--\r\n" % boundary).encode("utf-8")
        data = pre + file_bytes + post
        headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        sys.exit("Soniox %s %s -> HTTP %s: %s" % (method, path, e.code, detail))
    except urllib.error.URLError as e:
        sys.exit("Network error calling Soniox %s %s: %s" % (method, path, e))
    return json.loads(raw) if raw else {}


def build_transcripts(tokens):
    """Group consecutive tokens by speaker -> speaker-labeled lines, plus the flat
    text and the dominant language."""
    flat = []
    lines = []
    current = None
    buf = []
    lang_counts = {}

    def flush():
        text = "".join(buf).strip()
        if text:
            label = "Speaker ?" if current is None else "Speaker %s" % current
            lines.append("%s: %s" % (label, text))
        buf.clear()

    for t in tokens or []:
        piece = t.get("text", "")
        flat.append(piece)
        lang = t.get("language")
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        spk = t.get("speaker")
        if spk != current:
            flush()
            current = spk
        buf.append(piece)
    flush()

    language = "unknown"
    if lang_counts:
        language = max(lang_counts, key=lang_counts.get)
    return "".join(flat).strip(), "\n".join(lines), language


def main():
    ap = argparse.ArgumentParser(description="Transcribe an audio file with Soniox.")
    ap.add_argument("audio", help="path to the audio file (mp3/wav/m4a/...)")
    ap.add_argument("--outdir", help="output directory (default: same folder as the audio)")
    ap.add_argument(
        "--provider",
        choices=["soniox", "soniox-disfluencies"],
        default="soniox",
        help="soniox (default) = clean transcript; soniox-disfluencies keeps "
        "filler words / hesitations verbatim (אממ, אהה, um, uh)",
    )
    ap.add_argument("--model", default="stt-async-v5", help="Soniox model (default stt-async-v5)")
    ap.add_argument(
        "--language-hints",
        default="he,en",
        help='comma-separated language hints (default "he,en")',
    )
    ap.add_argument("--key", help="Soniox API key (overrides env/key file)")
    ap.add_argument("--key-file", help="path to a file containing the Soniox API key")
    ap.add_argument("--poll-seconds", type=int, default=5, help="seconds between status polls")
    ap.add_argument("--timeout-seconds", type=int, default=7200, help="give up after this long")
    ap.add_argument("--keep-remote", action="store_true", help="do not delete the uploaded file/job from Soniox")
    args = ap.parse_args()

    audio = args.audio
    if not os.path.isfile(audio):
        sys.exit("Audio file not found: " + audio)
    key = resolve_key(args)

    outdir = args.outdir or os.path.dirname(os.path.abspath(audio))
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(audio))[0]
    json_out = os.path.join(outdir, stem + "-soniox.json")
    flat_out = os.path.join(outdir, stem + ".txt")
    spk_out = os.path.join(outdir, stem + "-speakers.txt")

    size_mb = os.path.getsize(audio) / (1024 * 1024)
    log("Uploading %s (%.1f MB) to Soniox ..." % (os.path.basename(audio), size_mb))
    up = api("POST", "/v1/files", key, multipart=audio)
    file_id = up.get("id")
    if not file_id:
        sys.exit("Upload did not return a file id: " + json.dumps(up))
    log("Uploaded. file_id=%s" % file_id)

    req_body = {
        "model": args.model,
        "file_id": file_id,
        "enable_speaker_diarization": True,
        "enable_language_identification": True,
        "language_hints": [h.strip() for h in args.language_hints.split(",") if h.strip()],
    }
    if args.provider == "soniox-disfluencies":
        req_body["context"] = DISFLUENCY_CONTEXT

    created = api("POST", "/v1/transcriptions", key, body=req_body)
    tid = created.get("id")
    if not tid:
        sys.exit("Create transcription did not return an id: " + json.dumps(created))
    log("Transcription started. id=%s — polling every %ss ..." % (tid, args.poll_seconds))

    deadline = time.time() + args.timeout_seconds
    status = None
    while time.time() < deadline:
        job = api("GET", "/v1/transcriptions/" + tid, key)
        status = job.get("status")
        if status == "completed":
            break
        if status == "error":
            msg = job.get("error_message") or job.get("error_type") or "unknown Soniox error"
            sys.exit("Soniox transcription failed: " + msg)
        log("  status=%s ..." % status)
        time.sleep(args.poll_seconds)
    if status != "completed":
        sys.exit("Timed out after %ss (last status=%s)." % (args.timeout_seconds, status))

    log("Completed. Fetching transcript ...")
    result = api("GET", "/v1/transcriptions/" + tid + "/transcript", key)

    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    flat, speakers, language = build_transcripts(result.get("tokens"))
    with open(flat_out, "w", encoding="utf-8") as f:
        f.write(flat + "\n")
    with open(spk_out, "w", encoding="utf-8") as f:
        f.write(speakers + "\n")

    if not args.keep_remote:
        # Best-effort cleanup so files don't accumulate in the Soniox account.
        try:
            api("DELETE", "/v1/transcriptions/" + tid, key)
            api("DELETE", "/v1/files/" + file_id, key)
        except SystemExit:
            pass  # cleanup failures shouldn't fail the whole run

    log("Detected language: %s" % language)
    log("Wrote:")
    log("  " + json_out)
    log("  " + flat_out)
    log("  " + spk_out)
    # Emit a small machine-readable summary on stdout.
    print(json.dumps({
        "language": language,
        "json": json_out,
        "flat": flat_out,
        "speakers": spk_out,
        "chars": len(flat),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
