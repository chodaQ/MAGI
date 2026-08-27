import os
import platform
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# The kernel_build tests invoke a real merge_config.sh-style script,
# which needs GNU sed/coreutils. On macOS the system tools are BSD
# variants (see magi.builder.kernel_build.check_host_toolchain) -- if
# Homebrew's GNU versions are installed, prefer them here too, exactly
# as the README tells real users to. If they aren't installed, the
# affected tests will fail with the same actionable BuildError a real
# user would see, rather than a confusing unrelated failure.
if platform.system() == "Darwin":
    _gnu_dirs = [
        "/opt/homebrew/opt/coreutils/libexec/gnubin",
        "/opt/homebrew/opt/gnu-sed/libexec/gnubin",
        "/usr/local/opt/coreutils/libexec/gnubin",
        "/usr/local/opt/gnu-sed/libexec/gnubin",
    ]
    existing = [d for d in _gnu_dirs if Path(d).is_dir()]
    if existing:
        os.environ["PATH"] = os.pathsep.join(existing) + os.pathsep + os.environ.get("PATH", "")
