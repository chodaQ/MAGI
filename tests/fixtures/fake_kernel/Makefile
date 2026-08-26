# Minimal stand-in for a real Linux kernel Makefile, used only by
# tests/test_kernel_build.py to exercise MAGI's orchestration logic
# (the sequence of make/merge_config.sh invocations and how their
# output/errors are handled) without needing a multi-gigabyte real
# kernel source tree as a test fixture.

ARCH ?= x86_64

.PHONY: all allnoconfig olddefconfig

# Real kernel Makefiles default to the "all" target when `make` is run
# with no explicit target; mirror that here so build_kernel()'s plain
# `make ARCH=...` invocation exercises the same code path it would
# against a real tree.
all:
	@mkdir -p arch/x86/boot
	@printf 'FAKE-BZIMAGE-CONTENT\n' > arch/x86/boot/bzImage

allnoconfig:
	@echo "# fake allnoconfig baseline (ARCH=$(ARCH))" > .config
	@echo "CONFIG_64BIT=y" >> .config

olddefconfig:
	@sort -u -o .config .config
