"""Build one demo clip for the static Altercast demo (demo/site).

Steps (each measured, nothing hand-edited):
 1. cut the segment from the source video → site/clips/<id>/video.mp4 (+ original.mp3)
 2. run the real engine on it at live speed (engine.cli poc) → record.json
 3. Demucs: remove the commentators' voices, keep the crowd → site/clips/<id>/crowd.mp3
 4. speak every line in every character voice (running server /api/voices/{id}/say, with the
    engine's emotion), fitted to the line's slot (≤ 1.35× speed) → site/clips/<id>/lines/*.mp3
 5. write site/clips/<id>/clip.json and update site/clips.json

Usage (engine server running on :8000):
  .venv/bin/python demo/build_clip.py --src SRC --id fox-cfb --start 12 --end 72 \
      --title "..." --sport "..." --credit "..." --license "CC BY 3.0" --source-url URL
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "demo" / "site"
VOICES = ["am_adam", "bm_george", "am_michael", "af_bella"]
MAX_TEMPO = 1.35
SR = 44100
SERVER = "http://localhost:8000"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def ffmpeg_audio(src: Path, sr: int = SR) -> np.ndarray:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(out, dtype=np.float32).copy()


def to_mp3(x: np.ndarray, path: Path, sr: int = SR, kbps: int = 96) -> None:
    tmp = path.with_suffix(".tmp.wav")
    sf.write(tmp, x, sr)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-b:a", f"{kbps}k", str(path)])
    tmp.unlink()


def say(voice: str, text: str, emotion: str) -> bytes:
    req = urllib.request.Request(
        f"{SERVER}/api/voices/{voice}/say",
        data=json.dumps({"text": text[:300], "emotion": emotion}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=180).read()


def fit(wav: bytes, window: float, tmp: Path) -> tuple[np.ndarray, float]:
    tmp.write_bytes(wav)
    dur = sf.info(tmp).duration
    tempo = min(MAX_TEMPO, max(1.0, dur / max(0.5, window)))
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(tmp), "-filter:a", f"atempo={tempo:.3f}",
         "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout  # fmt: skip
    return np.frombuffer(out, dtype=np.float32).copy(), tempo


def voice_list(ids: list[str], offered: dict[str, dict[str, str]]) -> list[list[str]]:
    """[[voice_id, name, short description], …] for the demo's voice pickers."""
    out = []
    for v in ids:
        info = offered.get(v) or {}
        desc = (info.get("description") or "").split("·")[0].strip().rstrip(".")
        short = desc if len(desc) <= 26 else desc[:27].rsplit(" ", 1)[0].rstrip(",")
        out.append([v, info.get("name") or v, (short.lower() or "cloned voice")])
    return out


def crowd_bed(audio: np.ndarray) -> np.ndarray:
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    model = get_model("htdemucs")
    import librosa

    x = librosa.resample(audio, orig_sr=SR, target_sr=model.samplerate)
    wav = torch.from_numpy(np.stack([x, x]))[None]
    with torch.inference_mode():
        src = apply_model(model, wav, device="cpu", progress=False)[0]
    vi = model.sources.index("vocals")
    rest = sum(src[i] for i in range(len(model.sources)) if i != vi).mean(0).numpy()
    return librosa.resample(rest.astype(np.float32), orig_sr=model.samplerate, target_sr=SR)


def offered_voices() -> dict[str, dict[str, str]]:
    with urllib.request.urlopen(f"{SERVER}/api/voices", timeout=30) as r:
        return {v["voice_id"]: v for v in json.loads(r.read())}


def main() -> int:
    global SERVER
    p = argparse.ArgumentParser()
    for a in ("--src", "--id", "--title", "--sport", "--credit", "--license", "--source-url"):
        p.add_argument(a, required=True)
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--end", type=float, default=0.0)
    p.add_argument("--note", default="")
    p.add_argument("--speakers", type=int, default=2)
    p.add_argument("--config", default="", help="engine config, e.g. config/engine.loud.yaml")
    p.add_argument("--enroll", default="", help="config/enroll.<id>.yaml: a few seconds of each voice")
    p.add_argument("--record", default="", help="reuse an engine run folder instead of running again")
    p.add_argument("--voices", default=",".join(VOICES), help="voice ids, built-in or cloned (cu_…)")
    p.add_argument("--server", default="http://localhost:8000", help="engine server that speaks the voices")
    a = p.parse_args()
    SERVER = a.server.rstrip("/")
    voices = [v for v in a.voices.split(",") if v]

    out = SITE / "clips" / a.id
    (out / "lines").mkdir(parents=True, exist_ok=True)
    clip = ROOT / "data" / "clips" / f"demo_{a.id}.mp4"
    cut = ["-ss", str(a.start)] + (["-to", str(a.end)] if a.end else [])
    run(["ffmpeg", "-v", "error", "-y", *cut, "-i", a.src, "-vf", "scale=-2:'min(720,ih)'",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(clip)])  # fmt: skip
    run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-c", "copy", "-an", str(out / "video.mp4")])
    original = ffmpeg_audio(clip)
    duration = len(original) / SR
    to_mp3(original, out / "original.mp3", kbps=128)

    # 2. the real engine, at live speed
    if a.record:
        run_dir = Path(a.record)
    else:
        runs = ROOT / "outputs" / "demo_runs"
        before = set(runs.glob("*")) if runs.exists() else set()
        run([sys.executable, "-m", "engine.cli", "poc", "--clip", str(clip), "--speakers", str(a.speakers),
             "--out", str(runs), "--label", a.id, "--no-render",
             *(["--enroll", a.enroll] if a.enroll else []),
             *(["--config", a.config] if a.config else [])])  # fmt: skip
        run_dir = max(set(runs.glob("*")) - before, key=lambda d: d.stat().st_mtime)
    rec = json.loads((run_dir / "record.json").read_text())
    metrics = json.loads((run_dir / "metrics.json").read_text())

    # 3. crowd only (commentators removed)
    print("demucs: separating the crowd from the commentators …", flush=True)
    to_mp3(crowd_bed(original), out / "crowd.mp3", kbps=128)

    # 4. every line in every voice
    lines = [ln for ln in rec["lines"] if (ln.get("text") or "").strip()]
    spk_order = sorted({ln["speaker_id"] for ln in lines}, key=lambda s: min(
        ln["t_start"] for ln in lines if ln["speaker_id"] == s))  # fmt: skip
    spk_num = {s: i + 1 for i, s in enumerate(spk_order)}
    items = []
    tmp = out / "_tmp.wav"
    for i, ln in enumerate(lines):
        nxt = lines[i + 1]["t_start"] if i + 1 < len(lines) else duration
        window = max(ln["t_end"] - ln["t_start"], nxt - ln["t_start"] - 0.1)
        t = ln.get("times") or {}
        created = t.get("created")
        stage = lambda k: round(t[k] - created, 2) if created is not None and t.get(k) else None  # noqa: E731
        item = {
            "id": ln["line_id"], "start": round(ln["t_start"], 2), "end": round(ln["t_end"], 2),
            "speaker": spk_num[ln["speaker_id"]], "speaker_conf": ln.get("speaker_conf"),
            "emotion": ln.get("emotion") or "neutral", "arousal": round(ln.get("arousal") or 0, 2),
            "text": ln["text"].strip(), "asr_by": (ln.get("features") or {}).get("asr_by"),
            "stages": {"heard_after": round(created - ln["t_end"], 2) if created is not None else None,
                       "text": stage("asr_done"), "speaker": stage("speaker_done"),
                       "emotion": stage("emotion_done"), "voice": stage("tts_first")},
            "voices": {},
        }  # fmt: skip
        for v in voices:
            audio, tempo = fit(say(v, ln["text"], item["emotion"]), window, tmp)
            name = f"{ln['line_id']}_{v}.mp3"
            to_mp3(audio, out / "lines" / name, kbps=96)
            item["voices"][v] = {"file": f"lines/{name}", "dur": round(len(audio) / SR, 2),
                                 "tempo": round(tempo, 2)}  # fmt: skip
            print(f"  {ln['line_id']} S{item['speaker']} {v} tempo {tempo:.2f}", flush=True)
        items.append(item)
    tmp.unlink(missing_ok=True)

    d = metrics.get("delay", {})
    clip_json = {
        "id": a.id, "title": a.title, "sport": a.sport, "credit": a.credit, "license": a.license,
        "source_url": a.source_url, "note": a.note, "duration": round(duration, 2),
        "speakers": len(spk_num), "lines": items,
        "voice_list": voice_list(voices, offered_voices()),
        "speaker_names": {n: (rec.get("speakers", {}).get(s) or {}).get("display_name") or f"Speaker {n}"
                          for s, n in spk_num.items()},
        "engine": {"run": run_dir.name, "asr": (metrics.get("run") or {}).get("models", {}).get("asr"),
                   "felt_delay_p50": (d.get("delay_felt") or {}).get("p50"),
                   "felt_delay_p95": (d.get("delay_felt") or {}).get("p95"),
                   "view_delay_s": d.get("view_delay_s"),
                   "stages_p50": {k: v.get("p50") for k, v in (d.get("stages") or {}).items()}},
    }  # fmt: skip
    (out / "clip.json").write_text(json.dumps(clip_json, indent=1))
    index = SITE / "clips.json"
    allc = json.loads(index.read_text()) if index.exists() else []
    allc = [c for c in allc if c["id"] != a.id] + [
        {"id": a.id, "title": a.title, "sport": a.sport, "duration": round(duration, 1)}]  # fmt: skip
    index.write_text(json.dumps(allc, indent=1))
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(min(5, duration / 3)), "-i", str(out / "video.mp4"),
         "-frames:v", "1", "-vf", "scale=480:-2", str(out / "poster.jpg")])  # fmt: skip
    print(f"done → {out} ({len(items)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
