# Cloning voices and using them everywhere (app, extension, demo)

## Why the built-in voices sound flat
The four built-in characters (Hype Host, The Veteran, Coach, Spark) are Fish Audio copying a short
**Kokoro** recording, which is itself a computer voice. A copy of a computer voice still sounds like a
computer. A clone of a **real human recording** sounds human, keeps its accent and energy, and still
gets the engine's mood tags (calm / excited / peak).

## Which voices you may clone
| OK | Not OK |
|---|---|
| Your own voice | A real commentator, celebrity or politician |
| A friend or colleague who **agreed in writing** | A known character (Mickey Mouse, game or film characters) |
| A voice actor you hired **with an AI-voice licence** in the contract | Voices taken from YouTube, TV or podcasts |
| A recording sold with a licence that allows voice cloning | "Sounds like…" imitations of someone famous |

Every clone asks you to confirm permission (`consent`); the engine refuses without it.

## What to record (this decides the quality)
- **Instant clone:** 10–15 s of one person talking. Longer is not better here (measured: 15 s
  was closest; 29 s was less similar and slower).
- **Professional clone:** 1–10 min. The engine keeps only the main voice, drops noise, and picks
  the best calm, neutral and excited parts, so a real commentary session works well.
- Phone or headset mic, **quiet room**, no music, no crowd, no echo. One speaker only.
- **Talk like a commentator:** read a few play-by-play lines, including one excited call
  ("He shoots… and it's in!"). The clone copies the delivery, not just the timbre.
- Save as WAV, MP3, M4A or a video file; any of them works.

Script you can read (about 15 s):
> "Welcome back, everyone. Quick ball out to the left wing, he cuts inside, one defender beaten,
> two… he shoots — and it's in! What a finish! The whole stadium is on its feet!"

## Three ways to clone and control voices (same voice library behind all of them)
1. **Voice Studio (browser)** — the private Space `manishvk18/altercast-voice-studio`:
   **Clone a voice** → instant or professional → **In app / Hidden / Delete**. Saved to the
   private voice library dataset `manishvk18/altercast-voices`, so restarts never lose it.
2. **Terminal / backend** — on any server (this machine, the Studio Space, your own host):
   ```bash
   .venv/bin/python -m engine.cli voices list
   .venv/bin/python -m engine.cli voices add --name "Rio" --file rio.wav --i-have-permission
   .venv/bin/python -m engine.cli voices add-pro --name "Rio Pro" --file rio_5min.mp3 --i-have-permission
   .venv/bin/python -m engine.cli voices say cu_rio --text "What a goal!" --emotion excited --out goal.wav
   .venv/bin/python -m engine.cli voices hide cu_rio      # or: show / delete / sync
   ```
   `--server URL` (or `LCV_SERVER`) picks the server; `LCV_ACCESS_CODE` and `HF_TOKEN` are read
   from the environment when the server needs them.
3. **HTTP API** (for your own website or tools): `POST /api/voices/custom` (instant),
   `POST /api/voices/pro` + `GET /api/voices/jobs/{id}` (professional),
   `POST /api/voices/{id}/say`, `POST /api/voices/library/{id}` `{enabled}`,
   `DELETE /api/voices/custom/{id}`, `GET /api/voices`.

Every server that points at the same library (`LCV_VOICE_LIBRARY`) gets the voices within a
minute: the public app, the extension's hosted engine, a future website, or a folder
(`dir:/path`) if you leave Hugging Face.

## Putting a cloned voice into the demo page
The demo clips are pre-built, so a new voice is spoken for every line once and uploaded:
```bash
.venv/bin/python demo/add_voices.py --clip all --voices cu_rio,cu_maya --default 3=cu_rio
.venv/bin/python demo/add_voices.py --clip fox-cfb --remove am_michael     # drop a voice
```
The voice then shows in every speaker's picker (name and description from the library), and
`--default 3=cu_rio` makes it the first choice for speaker 3. New clips: `build_clip.py --voices …`.
