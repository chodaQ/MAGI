"""Capability -> Kconfig option mapping.

This is the curated knowledge base that turns "the program calls
socket()/bind()/listen()" into "the kernel needs CONFIG_NET=y and
CONFIG_INET=y". Every entry is deliberately conservative: options are
only listed here when the Linux kernel actually gates the
corresponding functionality behind them. Capabilities backed by
syscalls that are *always* compiled in (e.g. fork(), epoll, mmap) are
still listed, with an empty option list and a rationale explaining
why there is nothing to toggle -- that keeps the mapping table
auditable instead of silently dropping capabilities we detected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class Mapping:
    options: Tuple[str, ...]
    rationale: str


# Options required on every profile for a bootable, usable minimal
# kernel (console, root filesystem mounting, process execution).
# Sourced from the set of options tinyconfig/allnoconfig-derived
# minimal configs are documented to need in order to actually boot to
# a userspace init, rather than just link.
#
# CONFIG_SERIAL_8250(_CONSOLE) / CONFIG_SERIAL_AMBA_PL011(_CONSOLE) were
# added after a real QEMU boot test against a MAGI-generated .config
# (Linux 6.6.79, arm64) showed the kernel executing correctly -- real
# interrupt/PSCI traces confirmed via `-d int` -- but printing nothing
# at all: CONFIG_TTY/CONFIG_VT/CONFIG_VT_CONSOLE cover the virtual
# terminal layer but not any actual UART driver, so `console=ttyAMA0`
# (or `console=ttyS0` on x86) had no backing device and every printk
# went nowhere. Without a console driver, "boots to a shell" is not
# actually true even though the kernel runs -- there is nothing to
# see or interact with. Both driver Kconfig symbols are harmless to
# include unconditionally: Kconfig silently ignores an option that
# doesn't exist for the selected architecture (e.g. AMBA_PL011 has no
# effect in an x86_64 build), so listing both covers x86/i386 (8250)
# and arm/arm64 QEMU-virt-style targets (PL011) without needing
# per-arch branching here.
BASE_OPTIONS: Tuple[str, ...] = (
    "CONFIG_64BIT",
    "CONFIG_BINFMT_ELF",
    "CONFIG_BINFMT_SCRIPT",
    "CONFIG_BLK_DEV_INITRD",
    "CONFIG_DEVTMPFS",
    "CONFIG_DEVTMPFS_MOUNT",
    "CONFIG_TTY",
    "CONFIG_VT",
    "CONFIG_VT_CONSOLE",
    "CONFIG_UNIX98_PTYS",
    "CONFIG_SERIAL_8250",
    "CONFIG_SERIAL_8250_CONSOLE",
    "CONFIG_SERIAL_AMBA_PL011",
    "CONFIG_SERIAL_AMBA_PL011_CONSOLE",
    "CONFIG_PROC_FS",
    "CONFIG_SYSFS",
    "CONFIG_TMPFS",
    "CONFIG_PRINTK",
    "CONFIG_MULTIUSER",
)

CAPABILITY_MAP: Dict[str, Mapping] = {
    "network_inet": Mapping(
        ("CONFIG_NET", "CONFIG_INET"),
        "Core networking stack + IPv4/TCP/UDP protocol support.",
    ),
    "network_ipv6": Mapping(
        ("CONFIG_IPV6",),
        "IPv6 protocol support (built as a module or built-in on top of CONFIG_INET).",
    ),
    "network_unix_socket": Mapping(
        ("CONFIG_UNIX",),
        "AF_UNIX/AF_LOCAL socket family.",
    ),
    "network_raw": Mapping(
        ("CONFIG_PACKET",),
        "AF_PACKET raw packet sockets.",
    ),
    "network_netlink": Mapping(
        ("CONFIG_NET",),
        "Netlink is part of the core net subsystem gated by CONFIG_NET; "
        "there is no separate netlink-only toggle.",
    ),
    "network_tun_tap": Mapping(
        ("CONFIG_TUN",),
        "TUN/TAP virtual network device driver.",
    ),
    "filesystem_io": Mapping(
        ("CONFIG_BLOCK", "CONFIG_EXT4_FS"),
        "Block layer + a default root filesystem (ext4). Override with "
        "--root-fs if the target uses a different filesystem.",
    ),
    "filesystem_tmpfs": Mapping(
        ("CONFIG_TMPFS", "CONFIG_SHMEM"),
        "tmpfs / POSIX shared-memory-backed temporary storage.",
    ),
    "process_thread": Mapping(
        (),
        "fork/exec/pthread are implemented via always-built-in syscalls; "
        "the kernel has no Kconfig gate to disable process/thread creation.",
    ),
    "ipc_sysv": Mapping(
        ("CONFIG_SYSVIPC",),
        "System V IPC (shared memory, semaphores, message queues).",
    ),
    "ipc_posix_mq": Mapping(
        ("CONFIG_POSIX_MQUEUE",),
        "POSIX message queues.",
    ),
    "ipc_shared_mmap": Mapping(
        ("CONFIG_SHMEM",),
        "tmpfs-backed anonymous shared memory used by mmap(MAP_SHARED).",
    ),
    "io_epoll": Mapping(
        (),
        "epoll is always built in (no CONFIG_EPOLL gate in modern kernels).",
    ),
    "io_inotify": Mapping(
        ("CONFIG_INOTIFY_USER",),
        "inotify filesystem-change notification API.",
    ),
    "namespaces_cgroups": Mapping(
        (
            "CONFIG_NAMESPACES",
            "CONFIG_CGROUPS",
            "CONFIG_NET_NS",
            "CONFIG_PID_NS",
            "CONFIG_USER_NS",
            "CONFIG_UTS_NS",
            "CONFIG_IPC_NS",
        ),
        "Namespace and cgroup isolation primitives (containers, sandboxing).",
    ),
    "bpf": Mapping(
        ("CONFIG_BPF", "CONFIG_BPF_SYSCALL"),
        "eBPF program loading and verification.",
    ),
    "usb": Mapping(
        ("CONFIG_USB_SUPPORT", "CONFIG_USB"),
        "USB host controller + core USB subsystem.",
    ),
    "sound": Mapping(
        ("CONFIG_SOUND", "CONFIG_SND"),
        "Audio subsystem (ALSA).",
    ),
    "gpu_drm": Mapping(
        ("CONFIG_DRM",),
        "Direct Rendering Manager (GPU) subsystem.",
    ),
    "bluetooth": Mapping(
        ("CONFIG_BT",),
        "Bluetooth subsystem.",
    ),
    "wireless": Mapping(
        ("CONFIG_WIRELESS", "CONFIG_CFG80211"),
        "802.11 wireless networking configuration API.",
    ),
    "realtime_sched": Mapping(
        (),
        "SCHED_FIFO/SCHED_RR are always available; there is no separate "
        "Kconfig gate for real-time scheduling classes.",
    ),
    "block_device": Mapping(
        ("CONFIG_BLOCK",),
        "Block device layer for direct block device access.",
    ),
}
