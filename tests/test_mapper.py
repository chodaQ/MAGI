import pytest

from magi.analyzer.patterns import CAPABILITIES
from magi.mapper import BASE_OPTIONS, CAPABILITY_MAP, build_profile


def test_every_capability_has_a_mapping_entry():
    missing = set(CAPABILITIES) - set(CAPABILITY_MAP)
    assert not missing, f"capabilities with no Kconfig mapping: {missing}"


def test_base_options_always_present():
    profile = build_profile([])
    assert set(BASE_OPTIONS) <= set(profile.options)


def test_network_capability_maps_to_expected_options():
    profile = build_profile(["network_inet"])
    assert "CONFIG_NET" in profile.options
    assert "CONFIG_INET" in profile.options
    assert "CONFIG_SOUND" not in profile.options


def test_dedup_across_capabilities():
    profile = build_profile(["ipc_shared_mmap", "filesystem_tmpfs"])
    assert profile.options.count("CONFIG_SHMEM") == 1


def test_options_are_ordered_deterministically():
    p1 = build_profile(["bluetooth", "usb", "sound"])
    p2 = build_profile(["sound", "bluetooth", "usb"])
    assert p1.options == p2.options


def test_unmapped_capability_is_reported_not_raised():
    profile = build_profile(["totally_unknown_capability"])
    assert profile.unmapped_capabilities == ["totally_unknown_capability"]


def test_root_fs_override():
    profile = build_profile(["filesystem_io"], root_fs="btrfs")
    assert "CONFIG_BTRFS_FS" in profile.options
    assert "CONFIG_EXT4_FS" not in profile.options


def test_invalid_root_fs_raises():
    with pytest.raises(ValueError):
        build_profile(["filesystem_io"], root_fs="not-a-real-fs")


def test_trace_explains_every_option():
    profile = build_profile(["network_inet", "bluetooth"])
    for opt in profile.options:
        assert profile.trace.get(opt), f"{opt} has no rationale trace"
