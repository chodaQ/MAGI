from pathlib import Path

from magi.builder.config_generator import render_fragment, write_fragment
from magi.mapper import build_profile


def test_render_fragment_has_one_line_per_option():
    profile = build_profile(["network_inet"])
    text = render_fragment(profile)
    for opt in profile.options:
        assert f"{opt}=y" in text


def test_write_fragment_creates_parents(tmp_path):
    profile = build_profile(["network_inet"])
    out = tmp_path / "nested" / "dir" / "magi.config"
    result_path = write_fragment(profile, out)
    assert result_path == out
    assert out.is_file()
    content = out.read_text()
    assert "CONFIG_NET=y" in content


def test_fragment_is_merge_config_compatible_syntax():
    profile = build_profile(["network_inet", "bluetooth"])
    text = render_fragment(profile)
    config_lines = [l for l in text.splitlines() if l and not l.startswith("#")]
    for line in config_lines:
        assert line.endswith("=y")
        assert line.startswith("CONFIG_")
