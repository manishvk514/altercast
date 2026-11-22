"""engine.cli voices: parser wiring and the consent check (no server needed)."""

import pytest

from engine.cli import build_parser


def test_voices_commands_parse() -> None:
    p = build_parser()
    a = p.parse_args(["voices", "--server", "http://x:1", "add", "--name", "Rio", "--file", "a.wav",
                      "--i-have-permission"])  # fmt: skip
    assert a.voices_cmd == "add" and a.i_have_permission and a.server == "http://x:1"
    a = p.parse_args(["voices", "say", "cu_rio", "--text", "Goal!", "--emotion", "excited"])
    assert a.voice_id == "cu_rio" and a.emotion == "excited"
    for cmd in ("list", "sync"):
        assert p.parse_args(["voices", cmd]).voices_cmd == cmd


def test_clone_refused_without_permission(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = build_parser()
    a = p.parse_args(["voices", "add", "--name", "Rio", "--file", str(tmp_path / "a.wav")])
    with pytest.raises(SystemExit, match="permission"):
        a.func(a)
    a = p.parse_args(["voices", "add-pro", "--name", "Rio", "--file", str(tmp_path / "a.wav")])
    with pytest.raises(SystemExit, match="permission"):
        a.func(a)
