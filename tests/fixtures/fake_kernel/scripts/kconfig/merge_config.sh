#!/usr/bin/env bash
# Stub stand-in for the real kernel's scripts/kconfig/merge_config.sh,
# just enough to test MAGI's orchestration: append every CONFIG_*=y
# line found in the given fragment file(s) onto the base .config,
# de-duplicated. Not a faithful reimplementation (the real script also
# reports conflicting overrides); see tests/fixtures/fake_kernel/README.
set -euo pipefail

mode="$1"; shift
base="$1"; shift

for frag in "$@"; do
  grep -E '^CONFIG_[A-Za-z0-9_]+=y$' "$frag" >> "$base"
done
sort -u -o "$base" "$base"
