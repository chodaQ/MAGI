import re
from pathlib import Path

from magi.builder.config_generator import render_explanation, render_fragment, write_fragment
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


def test_fragment_has_no_per_option_comments():
    """Regression test: real merge_config.sh locates an option's value
    with `grep -w $CFG file`, a plain word match that is NOT
    comment-aware. A comment line mentioning the same CONFIG_ token
    (e.g. `# CONFIG_NET: reason` directly above `CONFIG_NET=y`) also
    matches, and gets concatenated with the real line by merge_config.sh,
    corrupting the merge. This was caught by running an actual kernel
    tree's merge_config.sh against MAGI's fragment output, not by
    reasoning about the format alone -- so keep this rule enforced."""
    profile = build_profile(["network_inet", "bluetooth", "usb"])
    text = render_fragment(profile)
    for opt in profile.options:
        # No comment line anywhere in the fragment may contain the
        # option name as a standalone word (mirrors grep -w).
        for line in text.splitlines():
            if line.startswith("#"):
                assert not re.search(rf"\b{re.escape(opt)}\b", line), (
                    f"comment line {line!r} mentions {opt}, which will "
                    "corrupt a real merge_config.sh run"
                )


def test_render_explanation_lists_rationale_separately():
    profile = build_profile(["network_inet"])
    fragment = render_fragment(profile)
    explanation = render_explanation(profile)
    assert "network_inet" not in fragment  # rationale text must not leak into the fragment
    assert "network_inet" in explanation
    assert "CONFIG_NET" in explanation
