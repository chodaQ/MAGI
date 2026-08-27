"""Command-line entry point: ``magi analyze`` / ``magi build``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .ai_assist import refine
from .analyzer import analyze_path
from .builder import (
    BuildError,
    boot_test,
    build_kernel,
    generate_dot_config,
    render_explanation,
    write_fragment,
)
from .mapper import build_profile


def _analyze(args) -> int:
    result = analyze_path(Path(args.path))
    if not args.no_ai:
        result = refine(result, model_path=args.model_path)

    caps = sorted(result.capabilities)
    if args.json:
        payload = {
            "files_scanned": result.files_scanned,
            "files_skipped": result.files_skipped,
            "capabilities": caps,
            "evidence": [
                {
                    "capability": e.capability,
                    "source": e.source,
                    "line": e.line,
                    "matched": e.matched,
                    "kind": e.kind,
                    "snippet": e.snippet,
                }
                for e in result.evidence
            ],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(f"scanned {result.files_scanned} file(s), skipped {result.files_skipped} unsupported file(s)")
    if not caps:
        print("no known kernel-facing capabilities detected")
        return 0
    print(f"\ndetected {len(caps)} capabilit{'y' if len(caps) == 1 else 'ies'}:")
    by_cap = result.by_capability()
    for cap in caps:
        evs = by_cap[cap]
        print(f"  - {cap}  ({len(evs)} match{'es' if len(evs) != 1 else ''})")
        for e in evs[:3]:
            label = f"{e.matched}()" if e.kind == "call" else e.matched
            print(f"      {e.source}:{e.line}  {label}  |  {e.snippet}")
        if len(evs) > 3:
            print(f"      ... and {len(evs) - 3} more")
    return 0


def _build(args) -> int:
    result = analyze_path(Path(args.path))
    if not args.no_ai:
        result = refine(result, model_path=args.model_path)

    profile = build_profile(result.capabilities, root_fs=args.root_fs)

    if profile.unmapped_capabilities:
        print(
            "warning: capabilities with no Kconfig mapping (skipped): "
            + ", ".join(profile.unmapped_capabilities),
            file=sys.stderr,
        )

    out_path = Path(args.out)
    write_fragment(profile, out_path)
    print(f"wrote Kconfig fragment: {out_path}  ({len(profile.options)} options)")

    if args.explain:
        print()
        print(render_explanation(profile))

    if not args.kernel_src:
        print("no --kernel-src given: stopping after fragment generation")
        return 0

    kernel_src = Path(args.kernel_src)
    try:
        report = generate_dot_config(kernel_src, out_path, arch=args.arch, cross_compile=args.cross_compile)
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f".config generated at {report.dot_config}")

    if args.build:
        try:
            report = build_kernel(
                kernel_src, arch=args.arch, jobs=args.jobs, report=report,
                cross_compile=args.cross_compile,
            )
        except BuildError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if report.image_path:
            print(f"built image: {report.image_path} ({report.image_size_bytes} bytes)")
        else:
            print("build finished but no recognized kernel image was found", file=sys.stderr)

        if args.boot_test:
            if not report.image_path:
                print("skipping boot test: no image to boot", file=sys.stderr)
            else:
                bt = boot_test(report.image_path, arch=args.arch)
                status = "PASS" if bt.passed else "FAIL"
                print(f"boot test: {status} ({bt.reason})")
                if not bt.ran or not bt.passed:
                    return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magi", description=__doc__)
    parser.add_argument("--version", action="version", version=f"magi {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("path", help="source file or directory to analyze")
    common.add_argument("--no-ai", action="store_true", help="disable the ai_assist refinement pass")
    common.add_argument("--model-path", default=None, help="path to an optional local GGUF model for deeper disambiguation")

    p_analyze = sub.add_parser("analyze", parents=[common], help="scan source and list detected capabilities")
    p_analyze.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    p_analyze.set_defaults(func=_analyze)

    p_build = sub.add_parser("build", parents=[common], help="generate a Kconfig fragment (and optionally build/boot it)")
    p_build.add_argument("--out", default="magi.config", help="output path for the generated Kconfig fragment")
    p_build.add_argument("--explain", action="store_true", help="print why each option was included")
    p_build.add_argument("--root-fs", default="ext4", choices=["ext4", "xfs", "btrfs", "vfat", "overlay", "squashfs"])
    p_build.add_argument("--kernel-src", default=None, help="path to a Linux kernel source tree; enables .config generation")
    p_build.add_argument("--arch", default="x86_64")
    p_build.add_argument("--cross-compile", default=None, help="cross-toolchain prefix, e.g. x86_64-linux-musl- (needed when building for an arch that doesn't match the host)")
    p_build.add_argument("--build", action="store_true", help="actually compile the kernel (requires --kernel-src)")
    p_build.add_argument("--boot-test", action="store_true", help="boot-smoke-test the built image under QEMU (requires --build)")
    p_build.add_argument("--jobs", type=int, default=None, help="parallel build jobs (default: make's default)")
    p_build.set_defaults(func=_build)

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
