"""MAGI - Minimal Attack-surface Generator for kernel Images.

Analyze source code, determine which kernel capabilities it actually
uses, and produce a minimal Kconfig fragment (and, optionally, a
buildable .config) for a Linux kernel that supports exactly that.
"""

__version__ = "0.1.0"
