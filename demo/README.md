# Altercast recorded demo (one clip)

Live: https://huggingface.co/spaces/manishvk18/altercast-demo

- `match.html` + `render_match.js` — the animated match (Playwright renders frames → ffmpeg).
- `data/scripts/demo_clip.yaml` — the commentary script; `scripts/make_synthetic_clip.py --script data/scripts/demo_clip.yaml --name demo_clip` makes the clip.
- The real engine processed the clip at live speed (Quality Lab run `20261122-055222_989c2a`:
  WER 3.9 %, speakers 94 %, emotion within one level 100 %, felt delay p50 0.16 s / p95 1.22 s, 6 s view buffer).
- Each line was voiced with `/api/voices/{id}/say` (2 voices per commentator, engine's emotion), fitted to its slot
  (≤ 1.35× speed, no overlaps) and mixed over a crowd bed → `site/audio/<c1>__<c2>.mp3`.
- `build_clip.py` — turns any clip into a demo clip: engine run at live speed, Demucs crowd-only track, every line in 4 voices.
- `site/` is the static Space (v2: real CC BY broadcast, live voice switching, who-said-what panel): upload it to a Space with `sdk: static`.
