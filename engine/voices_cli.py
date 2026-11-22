"""`python -m engine.cli voices …` — manage cloned voices from a terminal, on any Altercast server.

It talks to a server's HTTP API, so the same commands work on this machine (default
http://localhost:8000), on the private Voice Studio Space, or on any other host you run:

  voices list                                   every voice the server offers (built-in + cloned)
  voices add  --name "Rio" --file me.wav --i-have-permission      instant clone (6–15 s of speech)
  voices add-pro --name "Rio" --file 5min.mp3 --i-have-permission professional clone (1–10 min)
  voices say  cu_rio --text "What a goal!" --emotion excited --out goal.wav
  voices hide cu_rio  /  voices show cu_rio     offered in the app or not (kept in the library)
  voices delete cu_rio                          remove everywhere (library too)
  voices sync                                   fetch the latest library now

Where to point it: --server URL (or LCV_SERVER). A server with an access code needs
LCV_ACCESS_CODE; a private Hugging Face Space needs HF_TOKEN (read access is enough to list,
the Studio needs your write token to save). Keys are read from the environment, never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def _session(args: argparse.Namespace) -> tuple[Any, str]:
    import requests

    s = requests.Session()
    if code := os.environ.get("LCV_ACCESS_CODE"):
        s.headers["X-Access-Code"] = code
    server = (args.server or os.environ.get("LCV_SERVER") or "http://localhost:8000").rstrip("/")
    if ".hf.space" in server and (tok := os.environ.get("HF_TOKEN")):
        s.headers["Authorization"] = f"Bearer {tok}"  # private Spaces
    return s, server


def _ok(r: Any) -> Any:
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except ValueError:
            detail = r.text[:300]
        msg = detail.get("message") if isinstance(detail, dict) else detail
        raise SystemExit(f"error {r.status_code}: {msg}")
    return r


def _consent(args: argparse.Namespace) -> None:
    if not args.i_have_permission:
        raise SystemExit(
            "Add --i-have-permission to confirm the voice is yours or you have the speaker's "
            "permission (or a licence) to clone it. Never clone a real person or a known "
            "character without that."
        )


def cmd_list(args: argparse.Namespace) -> int:
    s, server = _session(args)
    voices = _ok(s.get(f"{server}/api/voices", timeout=30)).json()
    lib = _ok(s.get(f"{server}/api/voices/library", timeout=30)).json()
    shown = {v["voice_id"]: v for v in lib.get("voices", [])}
    if args.json:
        print(json.dumps({"voices": voices, "library": lib}, indent=1))
        return 0
    print(f"server  {server}")
    print(f"library {lib.get('backend') or 'none (voices live on this server only)'}"
          f" · role {lib.get('role')} · can edit {lib.get('can_edit')}")  # fmt: skip
    for v in voices:
        kind = (v.get("tier") or "instant") if v["custom"] else "built-in"
        extra = f" · test score {v['score']}" if v.get("score") is not None else ""
        print(f"  {v['voice_id']:<22} {v['name']:<16} {kind}{extra}  — {v['description']}")
    hidden = [k for k, m in shown.items() if m.get("enabled") is False]
    for k in hidden:
        print(f"  {k:<22} (hidden from the app)")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    _consent(args)
    s, server = _session(args)
    f = Path(args.file)
    with f.open("rb") as fh:
        r = s.post(
            f"{server}/api/voices/custom",
            data={"name": args.name, "consent": "true", "transcript": args.transcript or ""},
            files={"file": (f.name, fh)},
            timeout=300,
        )
    v = _ok(r).json()
    print(f"added {v['voice_id']} ({v['name']}): {v['description']}")
    return 0


def cmd_add_pro(args: argparse.Namespace) -> int:
    _consent(args)
    s, server = _session(args)
    f = Path(args.file)
    with f.open("rb") as fh:
        r = s.post(
            f"{server}/api/voices/pro",
            data={"name": args.name, "consent": "true"},
            files={"file": (f.name, fh)},
            timeout=900,
        )
    job = _ok(r).json()
    last = ""
    while job.get("stage") not in ("done", "error"):
        time.sleep(3)
        job = _ok(s.get(f"{server}/api/voices/jobs/{job['job_id']}", timeout=30)).json()
        pct = round(100 * (job.get("progress") or 0))
        line = f"{job.get('stage')} {pct}% {job.get('message') or ''}"
        if line != last:
            print(" ", line, flush=True)
            last = line
    if job["stage"] == "error":
        raise SystemExit(f"error: {job.get('error')}")
    res = job.get("result") or {}
    print(f"added {res.get('voice_id')} (professional)")
    return 0


def cmd_say(args: argparse.Namespace) -> int:
    s, server = _session(args)
    r = s.post(
        f"{server}/api/voices/{args.voice_id}/say",
        json={"text": args.text, "emotion": args.emotion},
        timeout=180,
    )
    Path(args.out).write_bytes(_ok(r).content)
    print(f"wrote {args.out}")
    return 0


def _set(args: argparse.Namespace, on: bool) -> int:
    s, server = _session(args)
    r = s.post(f"{server}/api/voices/library/{args.voice_id}", json={"enabled": on}, timeout=60)
    print(f"{args.voice_id}: {'offered in the app' if _ok(r).json()['enabled'] else 'hidden'}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    s, server = _session(args)
    _ok(s.delete(f"{server}/api/voices/custom/{args.voice_id}", timeout=60))
    print(f"deleted {args.voice_id}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    s, server = _session(args)
    r = _ok(s.post(f"{server}/api/voices/library/sync", timeout=120))
    print(json.dumps(r.json(), indent=1))
    return 0


def add_parser(sub: Any) -> None:
    v = sub.add_parser("voices", help="list / clone / test / hide / delete voices on a server")
    v.add_argument("--server", default=None, help="default $LCV_SERVER or http://localhost:8000")
    vs = v.add_subparsers(dest="voices_cmd", required=True)
    p = vs.add_parser("list")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)
    for name, fn, hint in (("add", cmd_add, "6–15 s of clean speech"),
                           ("add-pro", cmd_add_pro, "1–10 min recording")):  # fmt: skip
        p = vs.add_parser(name, help=f"clone a voice from {hint}")
        p.add_argument("--name", required=True)
        p.add_argument("--file", required=True)
        p.add_argument("--i-have-permission", action="store_true")
        if name == "add":
            p.add_argument("--transcript", default="", help="what is said (else transcribed)")
        p.set_defaults(func=fn)
    p = vs.add_parser("say", help="speak a line with a voice → WAV")
    p.add_argument("voice_id")
    p.add_argument("--text", required=True)
    p.add_argument("--emotion", default="neutral", choices=["calm", "neutral", "excited", "peak"])
    p.add_argument("--out", default="say.wav")
    p.set_defaults(func=cmd_say)
    for name, on in (("show", True), ("hide", False)):
        p = vs.add_parser(name, help=f"{'offer' if on else 'hide'} a cloned voice in the app")
        p.add_argument("voice_id")
        p.set_defaults(func=lambda a, on=on: _set(a, on))
    p = vs.add_parser("delete", help="remove a cloned voice (library too)")
    p.add_argument("voice_id")
    p.set_defaults(func=cmd_delete)
    p = vs.add_parser("sync", help="fetch the latest voice library now")
    p.set_defaults(func=cmd_sync)


if __name__ == "__main__":  # python -m engine.voices_cli voices …
    ap = argparse.ArgumentParser(prog="voices")
    add_parser(ap.add_subparsers(dest="command", required=True))
    a = ap.parse_args()
    sys.exit(a.func(a))
