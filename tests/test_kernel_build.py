import shutil
from pathlib import Path

import pytest

from magi.builder import (
    BuildError,
    boot_test,
    build_kernel,
    generate_dot_config,
    verify_kernel_tree,
    write_fragment,
)
from magi.builder.kernel_build import _BOOT_TEST_ARCH_CONFIG, check_host_toolchain
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


def test_check_host_toolchain_passes_with_gnu_tools_on_path():
    # By the time tests run, conftest.py has already put GNU sed/cp
    # ahead on PATH if this is macOS and Homebrew has them installed;
    # on Linux the system tools already are GNU. Either way this must
    # not raise.
    check_host_toolchain()


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


def test_cross_compile_prefix_is_passed_to_make(kernel_src, tmp_path):
    profile = build_profile(["network_inet"])
    fragment = write_fragment(profile, tmp_path / "magi.config")

    report = generate_dot_config(kernel_src, fragment, arch="x86_64", cross_compile="x86_64-linux-musl-")

    make_commands = [c for c in report.commands if c.args[0].endswith("make")]
    assert make_commands, "expected at least one make invocation"
    for cmd in make_commands:
        assert "CROSS_COMPILE=x86_64-linux-musl-" in cmd.args


def test_build_kernel_produces_image(kernel_src, tmp_path):
    profile = build_profile(["network_inet"])
    fragment = write_fragment(profile, tmp_path / "magi.config")
    report = generate_dot_config(kernel_src, fragment, arch="x86_64")

    report = build_kernel(kernel_src, arch="x86_64", report=report)

    assert report.image_path is not None
    assert report.image_path.is_file()
    assert report.image_size_bytes and report.image_size_bytes > 0


def test_boot_test_supports_arm64_and_arm():
    """Regression test: boot_test() originally only knew about
    x86_64/i386, so `boot_test(image, arch="arm64")` -- the exact call
    `magi build --arch arm64 --boot-test` makes -- silently mapped to
    "no QEMU boot test defined" instead of actually booting anything.
    Caught by actually running boot_test() against a real MAGI-built
    arm64 kernel under qemu-system-aarch64."""
    assert "arm64" in _BOOT_TEST_ARCH_CONFIG
    assert "arm" in _BOOT_TEST_ARCH_CONFIG
    assert _BOOT_TEST_ARCH_CONFIG["arm64"]["console"] == "ttyAMA0"
    assert "-M" in _BOOT_TEST_ARCH_CONFIG["arm64"]["extra_args"]


def test_boot_test_missing_image_does_not_raise():
    result = boot_test(Path("/nonexistent/image"), arch="x86_64")
    assert result.ran is False
    assert result.passed is False


def test_boot_test_unsupported_arch_does_not_raise(tmp_path):
    fake_image = tmp_path / "Image"
    fake_image.write_bytes(b"not a real kernel")
    result = boot_test(fake_image, arch="mips")
    assert result.ran is False
    assert "mips" in result.reason
