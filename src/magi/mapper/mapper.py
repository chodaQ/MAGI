"""Turn detected capabilities into a concrete, deduplicated Kconfig set."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Set

from .kconfig_map import BASE_OPTIONS, CAPABILITY_MAP


@dataclass
class Profile:
    """The output of mapping: an ordered, deduplicated option list plus
    a trace of *why* each option was included, for auditability."""

    options: List[str] = field(default_factory=list)
    # option -> list of human-readable reasons it was included
    trace: Dict[str, List[str]] = field(default_factory=dict)
    unmapped_capabilities: List[str] = field(default_factory=list)

    def as_config_lines(self) -> List[str]:
        return [f"{opt}=y" for opt in self.options]


def build_profile(capabilities: Iterable[str], root_fs: str = "ext4") -> Profile:
    """Map a set of capability ids to a Kconfig option profile.

    ``root_fs`` overrides the filesystem chosen for the
    ``filesystem_io`` capability (default: ext4). Unknown capability
    ids are recorded in ``unmapped_capabilities`` rather than raising,
    so a newer analyzer can run against an older mapping table without
    crashing -- callers should surface that list to the user.
    """
    seen: Set[str] = set(BASE_OPTIONS)
    ordered: List[str] = list(BASE_OPTIONS)
    trace: Dict[str, List[str]] = {opt: ["required to boot a minimal kernel"] for opt in BASE_OPTIONS}
    unmapped: List[str] = []

    for cap_id in sorted(set(capabilities)):
        mapping = CAPABILITY_MAP.get(cap_id)
        if mapping is None:
            unmapped.append(cap_id)
            continue

        options = mapping.options
        if cap_id == "filesystem_io" and root_fs != "ext4":
            options = tuple(_substitute_root_fs(opt, root_fs) for opt in options)

        for opt in options:
            if opt not in seen:
                seen.add(opt)
                ordered.append(opt)
            trace.setdefault(opt, []).append(f"{cap_id}: {mapping.rationale}")

    return Profile(options=ordered, trace=trace, unmapped_capabilities=unmapped)


_ROOT_FS_OPTIONS = {
    "ext4": "CONFIG_EXT4_FS",
    "xfs": "CONFIG_XFS_FS",
    "btrfs": "CONFIG_BTRFS_FS",
    "vfat": "CONFIG_VFAT_FS",
    "overlay": "CONFIG_OVERLAY_FS",
    "squashfs": "CONFIG_SQUASHFS",
}


def _substitute_root_fs(option: str, root_fs: str) -> str:
    if option != "CONFIG_EXT4_FS":
        return option
    try:
        return _ROOT_FS_OPTIONS[root_fs]
    except KeyError as exc:
        raise ValueError(
            f"unknown root filesystem {root_fs!r}; supported: {sorted(_ROOT_FS_OPTIONS)}"
        ) from exc
