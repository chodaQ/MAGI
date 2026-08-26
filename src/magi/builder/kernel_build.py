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

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


class BuildError(RuntimeError):
    pass


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


def generate_dot_config(
    kernel_src: Path,
    fragment_path: Path,
    arch: str = "x86_64",
) -> BuildReport:
    """Produce a fully resolved ``.config`` inside ``kernel_src``.

    Steps: start from the smallest valid baseline (``allnoconfig``),
    merge the MAGI-generated fragment on top, then run
    ``olddefconfig`` so the kernel's own Kconfig resolves any options
    that the fragment's choices imply (dependencies, reverse selects).
    """
    kernel_src = Path(kernel_src)
    fragment_path = Path(fragment_path)
    verify_kernel_tree(kernel_src)
    if not fragment_path.is_file():
        raise BuildError(f"fragment file not found: {fragment_path}")

    commands: List[CommandResult] = []
    make = shutil.which("make")
    if make is None:
        raise BuildError("`make` not found on PATH")

    commands.append(_run([make, f"ARCH={arch}", "allnoconfig"], cwd=kernel_src))
    commands.append(
        _run(
            ["bash", "scripts/kconfig/merge_config.sh", "-m", ".config", str(fragment_path)],
            cwd=kernel_src,
        )
    )
    commands.append(_run([make, f"ARCH={arch}", "olddefconfig"], cwd=kernel_src))

    dot_config = kernel_src / ".config"
    if not dot_config.is_file():
        raise BuildError("olddefconfig completed but .config was not produced")

    return BuildReport(dot_config=dot_config, commands=commands)


def build_kernel(
    kernel_src: Path,
    arch: str = "x86_64",
    jobs: Optional[int] = None,
    report: Optional[BuildReport] = None,
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

    args = [make, f"ARCH={arch}"]
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


def boot_test(image_path: Path, arch: str = "x86_64", timeout: float = 30.0) -> BootTestResult:
    """Best-effort smoke test: boot the built image under QEMU with no
    root filesystem attached, and check that the kernel actually
    started executing (it will print its own "Linux version ..."
    banner within the first fraction of a second of real boot, well
    before it panics looking for an init process). This proves the
    generated .config produces a kernel that *runs*, without requiring
    MAGI to also synthesize a bootable root filesystem.
    """
    qemu_bin = {"x86_64": "qemu-system-x86_64", "i386": "qemu-system-i386"}.get(arch)
    if qemu_bin is None:
        return BootTestResult(ran=False, passed=False, reason=f"no QEMU boot test defined for arch={arch}")

    qemu = shutil.which(qemu_bin)
    if qemu is None:
        return BootTestResult(ran=False, passed=False, reason=f"{qemu_bin} not found on PATH")

    image_path = Path(image_path)
    if not image_path.is_file():
        return BootTestResult(ran=False, passed=False, reason=f"image not found: {image_path}")

    args = [
        qemu, "-kernel", str(image_path),
        "-nographic", "-no-reboot", "-m", "256",
        "-append", "console=ttyS0 panic=-1",
    ]
    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, timeout=timeout)
        log = proc.stdout
    except subprocess.TimeoutExpired as exc:
        log = (exc.stdout or "")

    if "Linux version" in log:
        return BootTestResult(ran=True, passed=True, reason="kernel banner observed under QEMU", log=log)
    return BootTestResult(ran=True, passed=False, reason="kernel did not print its boot banner", log=log)
