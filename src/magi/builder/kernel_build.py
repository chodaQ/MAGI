"""Drive an actual Linux kernel source tree through the merge/build/boot
pipeline.

This module shells out to standard kernel build tooling
(``make ... allnoconfig``, ``scripts/kconfig/merge_config.sh``,
``make ... olddefconfig``, ``make``) rather than reimplementing Kconfig
resolution -- that logic is intricate (option dependencies, reverse
selects, arch-specific defaults) and the kernel tree already ships the
canonical implementation. MAGI's job is orchestration and capability
detection, not reinventing Kconfig.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


class BuildError(RuntimeError):
    pass


def check_host_toolchain() -> None:
    """Fail fast, with an actionable message, instead of letting a BSD
    ``sed``/``cp`` silently corrupt a real merge_config.sh run.

    scripts/kconfig/merge_config.sh (part of every kernel tree) uses
    GNU-only invocations -- ``sed -i SCRIPT file`` (BSD sed requires an
    explicit, possibly-empty backup-suffix argument, so it instead
    treats the sed script as that suffix and the target file as the
    script) and ``cp -T`` (not a BSD cp flag at all). On macOS, whose
    system ``/usr/bin/sed`` and ``/usr/bin/cp`` are BSD tools, this
    fails: the first form silently drops the merge (visible only as a
    "sed: invalid command code" line buried in the log and a
    same-as-before .config), and the second form errors outright. This
    was found by actually running merge_config.sh from a real kernel
    tree during development, not by inspecting the script.
    """
    if platform.system() != "Darwin":
        return
    problems = []
    for tool in ("sed", "cp"):
        path = shutil.which(tool)
        if not path:
            continue
        try:
            out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
            is_gnu = "GNU" in out.stdout
        except (OSError, subprocess.TimeoutExpired):
            is_gnu = False
        if not is_gnu:
            problems.append((tool, path))
    if problems:
        tools = ", ".join(f"{t} ({p})" for t, p in problems)
        raise BuildError(
            f"macOS's BSD {tools} on PATH are incompatible with the kernel's "
            "scripts/kconfig/merge_config.sh (it needs GNU sed/coreutils). "
            "Install them and put them ahead of the system tools on PATH, e.g.:\n"
            "  brew install gnu-sed coreutils\n"
            '  export PATH="/opt/homebrew/opt/coreutils/libexec/gnubin:'
            '/opt/homebrew/opt/gnu-sed/libexec/gnubin:$PATH"'
        )


@dataclass
class CommandResult:
    args: List[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass
class BuildReport:
    dot_config: Path
    commands: List[CommandResult] = field(default_factory=list)
    image_path: Optional[Path] = None
    image_size_bytes: Optional[int] = None


@dataclass
class BootTestResult:
    ran: bool
    passed: bool
    reason: str
    log: str = ""


_IMAGE_CANDIDATES = {
    "x86_64": ["arch/x86/boot/bzImage"],
    "i386": ["arch/x86/boot/bzImage"],
    "arm64": ["arch/arm64/boot/Image", "arch/arm64/boot/Image.gz"],
    "arm": ["arch/arm/boot/zImage"],
}


def verify_kernel_tree(kernel_src: Path) -> None:
    kernel_src = Path(kernel_src)
    makefile = kernel_src / "Makefile"
    merge_script = kernel_src / "scripts" / "kconfig" / "merge_config.sh"
    if not makefile.is_file():
        raise BuildError(f"{kernel_src} does not look like a kernel source tree (no Makefile)")
    if not merge_script.is_file():
        raise BuildError(
            f"{kernel_src} is missing scripts/kconfig/merge_config.sh "
            "(expected in any Linux >= 3.x source tree)"
        )


def _run(args: List[str], cwd: Path, env=None) -> CommandResult:
    proc = subprocess.run(
        args, cwd=str(cwd), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    result = CommandResult(args=args, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
    if proc.returncode != 0:
        raise BuildError(
            f"command failed ({proc.returncode}): {' '.join(args)}\n--- stderr ---\n{proc.stderr}"
        )
    return result


def _cross_compile_args(cross_compile: Optional[str]) -> List[str]:
    return [f"CROSS_COMPILE={cross_compile}"] if cross_compile else []


def generate_dot_config(
    kernel_src: Path,
    fragment_path: Path,
    arch: str = "x86_64",
    cross_compile: Optional[str] = None,
) -> BuildReport:
    """Produce a fully resolved ``.config`` inside ``kernel_src``.

    Steps: start from the smallest valid baseline (``allnoconfig``),
    merge the MAGI-generated fragment on top, then run
    ``olddefconfig`` so the kernel's own Kconfig resolves any options
    that the fragment's choices imply (dependencies, reverse selects).

    ``cross_compile`` is the standard kernel build cross-toolchain
    prefix (e.g. ``x86_64-linux-musl-``) needed whenever the host
    architecture doesn't match ``arch`` -- for instance building an
    x86_64 kernel from an Apple Silicon Mac.
    """
    kernel_src = Path(kernel_src)
    fragment_path = Path(fragment_path)
    verify_kernel_tree(kernel_src)
    check_host_toolchain()
    if not fragment_path.is_file():
        raise BuildError(f"fragment file not found: {fragment_path}")

    commands: List[CommandResult] = []
    make = shutil.which("make")
    if make is None:
        raise BuildError("`make` not found on PATH")

    cc_args = _cross_compile_args(cross_compile)
    commands.append(_run([make, f"ARCH={arch}", *cc_args, "allnoconfig"], cwd=kernel_src))
    commands.append(
        _run(
            ["bash", "scripts/kconfig/merge_config.sh", "-m", ".config", str(fragment_path)],
            cwd=kernel_src,
        )
    )
    commands.append(_run([make, f"ARCH={arch}", *cc_args, "olddefconfig"], cwd=kernel_src))

    dot_config = kernel_src / ".config"
    if not dot_config.is_file():
        raise BuildError("olddefconfig completed but .config was not produced")

    return BuildReport(dot_config=dot_config, commands=commands)


def build_kernel(
    kernel_src: Path,
    arch: str = "x86_64",
    jobs: Optional[int] = None,
    report: Optional[BuildReport] = None,
    cross_compile: Optional[str] = None,
) -> BuildReport:
    """Actually compile the kernel image. Requires a working cross/native
    toolchain for ``arch`` on the host; this is the slow, real build
    step and is opt-in (call it only when the caller wants a bootable
    image, not just a validated .config)."""
    kernel_src = Path(kernel_src)
    verify_kernel_tree(kernel_src)
    make = shutil.which("make")
    if make is None:
        raise BuildError("`make` not found on PATH")

    args = [make, f"ARCH={arch}", *_cross_compile_args(cross_compile)]
    if jobs:
        args.append(f"-j{jobs}")
    result = _run(args, cwd=kernel_src)

    report = report or BuildReport(dot_config=kernel_src / ".config")
    report.commands.append(result)

    for candidate in _IMAGE_CANDIDATES.get(arch, []):
        image = kernel_src / candidate
        if image.is_file():
            report.image_path = image
            report.image_size_bytes = image.stat().st_size
            break

    return report


# Per-arch QEMU invocation. Verified for real by actually booting a
# MAGI-built arm64 kernel under qemu-system-aarch64 during development
# (see README, "실제 리눅스 커널 소스로 검증한 기록"): -M virt and
# console=ttyAMA0 are both required for arm/arm64 -- qemu-system-aarch64
# has no usable default machine type, and the QEMU virt board's UART is
# ttyAMA0 (PL011), not ttyS0. The x86_64/i386 entries need neither.
_BOOT_TEST_ARCH_CONFIG = {
    "x86_64": {"qemu_bin": "qemu-system-x86_64", "console": "ttyS0", "extra_args": []},
    "i386": {"qemu_bin": "qemu-system-i386", "console": "ttyS0", "extra_args": []},
    "arm64": {"qemu_bin": "qemu-system-aarch64", "console": "ttyAMA0", "extra_args": ["-M", "virt", "-cpu", "cortex-a72"]},
    "arm": {"qemu_bin": "qemu-system-arm", "console": "ttyAMA0", "extra_args": ["-M", "virt", "-cpu", "cortex-a15"]},
}


def boot_test(image_path: Path, arch: str = "x86_64", timeout: float = 30.0) -> BootTestResult:
    """Best-effort smoke test: boot the built image under QEMU with no
    root filesystem attached, and check that the kernel actually
    started executing (it will print its own "Linux version ..."
    banner within the first fraction of a second of real boot, well
    before it panics looking for an init process). This proves the
    generated .config produces a kernel that *runs*, without requiring
    MAGI to also synthesize a bootable root filesystem.
    """
    arch_config = _BOOT_TEST_ARCH_CONFIG.get(arch)
    if arch_config is None:
        return BootTestResult(ran=False, passed=False, reason=f"no QEMU boot test defined for arch={arch}")

    qemu = shutil.which(arch_config["qemu_bin"])
    if qemu is None:
        return BootTestResult(ran=False, passed=False, reason=f"{arch_config['qemu_bin']} not found on PATH")

    image_path = Path(image_path)
    if not image_path.is_file():
        return BootTestResult(ran=False, passed=False, reason=f"image not found: {image_path}")

    args = [
        qemu, *arch_config["extra_args"],
        "-kernel", str(image_path),
        "-display", "none", "-serial", "stdio", "-monitor", "none",
        "-no-reboot", "-m", "256",
        "-append", f"console={arch_config['console']} panic=-1",
    ]
    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, timeout=timeout)
        log = proc.stdout
    except subprocess.TimeoutExpired as exc:
        # exc.stdout is documented as decoded text when text=True is
        # passed to run(), but on the timeout path some Python versions
        # hand back the raw bytes captured before decoding was applied
        # -- decode defensively rather than crash on `in` over bytes.
        log = exc.stdout or ""
        if isinstance(log, bytes):
            log = log.decode("utf-8", errors="replace")

    if "Linux version" in log:
        return BootTestResult(ran=True, passed=True, reason="kernel banner observed under QEMU", log=log)
    return BootTestResult(ran=True, passed=False, reason="kernel did not print its boot banner", log=log)
