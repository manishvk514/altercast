"""Add (or remove) voices on demo clips that are already built — no new engine run needed.

Every line of the clip is spoken again in each new voice (with the engine's emotion for that
line), fitted to its slot exactly like build_clip.py, and the voice appears in the demo's voice
pickers. Any voice the server offers works: built-in characters or cloned voices (cu_…) from the
voice library.

  .venv/bin/python demo/add_voices.py --clip fox-cfb --voices cu_rio,cu_maya
  .venv/bin/python demo/add_voices.py --clip all --voices cu_rio --default 1=cu_rio
  .venv/bin/python demo/add_voices.py --clip fox-cfb --remove am_michael

--server picks the engine server (default http://localhost:8000, the one with your voices).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_clip as bc


def server_voices(server: str) -> dict[str, dict[str, str]]:
    import urllib.request

    with urllib.request.urlopen(f"{server}/api/voices", timeout=30) as r:
        return {v["voice_id"]: v for v in json.loads(r.read())}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--clip", required=True, help="clip id, or 'all'")
    p.add_argument("--voices", default="", help="comma-separated voice ids to add")
    p.add_argument("--remove", default="", help="comma-separated voice ids to drop")
    p.add_argument("--default", default="", help="e.g. 1=cu_rio,2=am_adam (speaker → voice)")
    p.add_argument("--server", default="http://localhost:8000")
    p.add_argument("--redo", action="store_true", help="re-voice even if the voice is there")
    a = p.parse_args()
    server = a.server.rstrip("/")
    bc.SERVER = server
    offered = server_voices(server)
    add = [v for v in a.voices.split(",") if v]
    drop = {v for v in a.remove.split(",") if v}
    for v in add:
        if v not in offered:
            raise SystemExit(f"{v} is not offered by {server} (see: engine.cli voices list)")
    ids = ([c["id"] for c in json.loads((bc.SITE / "clips.json").read_text())]
           if a.clip == "all" else [a.clip])  # fmt: skip
    for cid in ids:
        out = bc.SITE / "clips" / cid
        cj = json.loads((out / "clip.json").read_text())
        vlist = cj.get("voice_list") or bc.voice_list(list(cj["lines"][0]["voices"]), offered)
        tmp = out / "_tmp.wav"
        for i, ln in enumerate(cj["lines"]):
            nxt = cj["lines"][i + 1]["start"] if i + 1 < len(cj["lines"]) else cj["duration"]
            window = max(ln["end"] - ln["start"], nxt - ln["start"] - 0.1)
            for v in add:
                if v in ln["voices"] and not a.redo:
                    continue
                audio, tempo = bc.fit(bc.say(v, ln["text"], ln["emotion"]), window, tmp)
                name = f"{ln['id']}_{v}.mp3"
                bc.to_mp3(audio, out / "lines" / name, kbps=96)
                ln["voices"][v] = {"file": f"lines/{name}", "dur": round(len(audio) / bc.SR, 2),
                                   "tempo": round(tempo, 2)}  # fmt: skip
                print(f"  {cid} {ln['id']} {v} tempo {tempo:.2f}", flush=True)
            for v in drop:
                info = ln["voices"].pop(v, None)
                if info:
                    (out / info["file"]).unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)
        have = {x[0] for x in vlist}
        vlist += bc.voice_list([v for v in add if v not in have], offered)
        cj["voice_list"] = [x for x in vlist if x[0] not in drop]
        if a.default:
            cj["default_voices"] = {k: v for k, v in (x.split("=") for x in a.default.split(","))}
        (out / "clip.json").write_text(json.dumps(cj, indent=1))
        print(f"{cid}: voices → {', '.join(x[1] for x in cj['voice_list'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
