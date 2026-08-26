"""Capability pattern database.

Each entry describes one *kernel capability* (a coherent chunk of
kernel functionality, e.g. "the program opens TCP/IPv4 sockets") and
the concrete C function names / Python qualified calls that indicate a
program uses it.

This module intentionally has zero third-party dependencies: the
database is plain Python data so the analyzer can run anywhere Python
itself runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet


@dataclass(frozen=True)
class Capability:
    id: str
    description: str
    # Bare C identifiers that, if called, indicate this capability.
    c_calls: FrozenSet[str] = field(default_factory=frozenset)
    # Dotted Python call targets, e.g. "os.fork", "socket.socket".
    # A bare name with no dot (e.g. "open") matches Python's builtins.
    python_calls: FrozenSet[str] = field(default_factory=frozenset)
    # C preprocessor / literal tokens whose presence adds corroborating
    # evidence (e.g. AF_INET6 strengthens "network_ipv6"). Optional.
    c_tokens: FrozenSet[str] = field(default_factory=frozenset)


def _cap(id_, description, c_calls=(), python_calls=(), c_tokens=()):
    return Capability(
        id=id_,
        description=description,
        c_calls=frozenset(c_calls),
        python_calls=frozenset(python_calls),
        c_tokens=frozenset(c_tokens),
    )


CAPABILITIES = {
    c.id: c
    for c in [
        _cap(
            "network_inet",
            "TCP/UDP over IPv4/IPv6 socket I/O",
            c_calls={
                "socket", "bind", "listen", "accept", "accept4", "connect",
                "send", "recv", "sendto", "recvfrom", "sendmsg", "recvmsg",
                "getaddrinfo", "setsockopt", "getsockopt", "shutdown",
            },
            python_calls={
                "socket.socket", "socket.create_connection",
                "socket.create_server", "socket.getaddrinfo",
                "asyncio.open_connection", "asyncio.start_server",
            },
            c_tokens={"AF_INET", "AF_INET6", "SOCK_STREAM", "SOCK_DGRAM"},
        ),
        _cap(
            "network_ipv6",
            "IPv6 networking",
            c_tokens={"AF_INET6", "PF_INET6", "IN6ADDR_ANY_INIT"},
        ),
        _cap(
            "network_unix_socket",
            "AF_UNIX local sockets / IPC over sockets",
            python_calls={"socket.AF_UNIX"},
            c_tokens={"AF_UNIX", "AF_LOCAL"},
        ),
        _cap(
            "network_raw",
            "Raw / packet sockets (requires elevated privilege)",
            c_tokens={"AF_PACKET", "SOCK_RAW"},
        ),
        _cap(
            "network_netlink",
            "Netlink sockets (talking to the kernel networking stack)",
            c_tokens={"AF_NETLINK", "NETLINK_ROUTE"},
        ),
        _cap(
            "network_tun_tap",
            "TUN/TAP virtual network devices",
            c_tokens={"IFF_TUN", "IFF_TAP", "TUNSETIFF"},
        ),
        _cap(
            "filesystem_io",
            "Regular file I/O (open/read/write on a filesystem)",
            c_calls={
                "open", "openat", "creat", "read", "write", "pread",
                "pwrite", "close", "fopen", "fread", "fwrite", "fclose",
                "stat", "fstat", "lstat", "unlink", "rename", "mkdir",
                "rmdir", "chmod", "chown",
            },
            python_calls={
                "open", "os.open", "os.mkdir", "os.makedirs", "os.remove",
                "os.rename", "os.stat", "io.open", "pathlib.Path",
                "sqlite3.connect",
            },
        ),
        _cap(
            "filesystem_tmpfs",
            "Explicit use of a memory-backed tmpfs/shm path",
            c_tokens={"/dev/shm", "/tmp"},
            python_calls={"tempfile.TemporaryFile", "tempfile.mkstemp",
                          "multiprocessing.shared_memory.SharedMemory"},
        ),
        _cap(
            "process_thread",
            "Process/thread creation and control",
            c_calls={
                "fork", "vfork", "clone", "execve", "execvp", "execl",
                "pthread_create", "pthread_join", "pthread_mutex_lock",
                "waitpid", "wait",
            },
            python_calls={
                "os.fork", "os.exec", "subprocess.Popen", "subprocess.run",
                "subprocess.call", "threading.Thread",
                "multiprocessing.Process",
            },
        ),
        _cap(
            "ipc_sysv",
            "System V IPC (shared memory / semaphores / message queues)",
            c_calls={"shmget", "shmat", "shmdt", "semget", "semop", "msgget", "msgsnd", "msgrcv"},
        ),
        _cap(
            "ipc_posix_mq",
            "POSIX message queues",
            c_calls={"mq_open", "mq_send", "mq_receive"},
        ),
        _cap(
            "ipc_shared_mmap",
            "Shared memory via mmap(MAP_SHARED)",
            c_calls={"mmap", "munmap", "shm_open"},
            c_tokens={"MAP_SHARED"},
            python_calls={"mmap.mmap"},
        ),
        _cap(
            "io_epoll",
            "Scalable I/O event notification (epoll)",
            c_calls={"epoll_create", "epoll_create1", "epoll_ctl", "epoll_wait"},
            python_calls={"select.epoll"},
        ),
        _cap(
            "io_inotify",
            "Filesystem change notification (inotify)",
            c_calls={"inotify_init", "inotify_init1", "inotify_add_watch"},
            python_calls={"inotify_simple.INotify"},
        ),
        _cap(
            "namespaces_cgroups",
            "Linux namespaces / cgroups (containers, sandboxing)",
            c_calls={"unshare", "setns"},
            c_tokens={"CLONE_NEWNET", "CLONE_NEWPID", "CLONE_NEWNS", "CLONE_NEWUSER"},
        ),
        _cap(
            "bpf",
            "eBPF program loading",
            c_calls={"bpf"},
            python_calls={"bcc.BPF"},
        ),
        _cap(
            "usb",
            "USB device access",
            python_calls={"usb.core.find", "pyusb.core.find"},
            c_tokens={"/dev/bus/usb", "libusb_open"},
        ),
        _cap(
            "sound",
            "Audio subsystem (ALSA/OSS)",
            c_calls={"snd_pcm_open"},
            python_calls={"pyaudio.PyAudio", "sounddevice.play"},
            c_tokens={"/dev/snd", "SND_PCM"},
        ),
        _cap(
            "gpu_drm",
            "Direct Rendering Manager / GPU access",
            c_tokens={"/dev/dri", "drmOpen"},
        ),
        _cap(
            "bluetooth",
            "Bluetooth sockets",
            c_tokens={"AF_BLUETOOTH", "BTPROTO_HCI"},
        ),
        _cap(
            "wireless",
            "802.11 wireless networking control",
            c_tokens={"NL80211", "/proc/net/wireless"},
        ),
        _cap(
            "realtime_sched",
            "Real-time scheduling policies",
            c_calls={"sched_setscheduler", "sched_setattr"},
            c_tokens={"SCHED_FIFO", "SCHED_RR"},
        ),
        _cap(
            "block_device",
            "Direct block device access",
            c_tokens={"/dev/sd", "/dev/nvme", "BLKGETSIZE"},
        ),
    ]
}
