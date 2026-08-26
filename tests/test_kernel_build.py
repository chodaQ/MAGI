import shutil
from pathlib import Path

import pytest

from magi.builder import BuildError, build_kernel, generate_dot_config, verify_kernel_tree, write_fragment
from magi.mapper import build_profile

FAKE_KERNEL = Path(__file__).parent / "fixtures" / "fake_kernel"


@pytest.fixture
def kernel_src(tmp_path):
    dest = tmp_path / "fake_kernel"
    shutil.copytree(FAKE_KERNEL, dest)
    return dest


def test_verify_kernel_tree_accepts_valid_tree(kernel_src):
    verify_kernel_tree(kernel_src)  # must not raise


def test_verify_kernel_tree_rejects_missing_makefile(tmp_path):
    with pytest.raises(BuildError):
        verify_kernel_tree(tmp_path)


def test_generate_dot_config_produces_expected_options(kernel_src, tmp_path):
    profile = build_profile(["network_inet", "ipc_sysv"])
    fragment = write_fragment(profile, tmp_path / "magi.config")

    report = generate_dot_config(kernel_src, fragment, arch="x86_64")

    assert report.dot_config.is_file()
    content = report.dot_config.read_text()
    assert "CONFIG_NET=y" in content
    assert "CONFIG_INET=y" in content
    assert "CONFIG_SYSVIPC=y" in content
    # base options must survive the merge too
    assert "CONFIG_64BIT=y" in content
    assert len(report.commands) == 3  # allnoconfig, merge_config.sh, olddefconfig


def test_generate_dot_config_missing_fragment_raises(kernel_src):
    with pytest.raises(BuildError):
        generate_dot_config(kernel_src, kernel_src / "does_not_exist.config")


def test_build_kernel_produces_image(kernel_src, tmp_path):
    profile = build_profile(["network_inet"])
    fragment = write_fragment(profile, tmp_path / "magi.config")
    report = generate_dot_config(kernel_src, fragment, arch="x86_64")

    report = build_kernel(kernel_src, arch="x86_64", report=report)

    assert report.image_path is not None
    assert report.image_path.is_file()
    assert report.image_size_bytes and report.image_size_bytes > 0
