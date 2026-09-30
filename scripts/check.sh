#!/usr/bin/env bash
# This repo's "done" check: the contract's files agree, the launcher works, and the clients' real
# binaries answer as the contract says.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 contract/transcript.py --check
sh -n skills/unfold/scripts/unfold
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck --shell=sh skills/unfold/scripts/unfold
else
  echo "shellcheck isn't installed: skipping it"
fi

# The conformance tests run the Linux client's binary, which builds and runs on macOS too.
linux=../unfold-omarchy
if [ -n "${UNFOLD_LINUX_BIN:-}" ]; then
  echo "using the Linux client at $UNFOLD_LINUX_BIN"
elif [ -d "$linux" ] && command -v cargo >/dev/null 2>&1; then
  echo "building the Linux client's debug binary"
  # On macOS GTK comes from Homebrew, as in that repo's Makefile.
  if [ "$(uname -s)" = Darwin ]; then
    export PKG_CONFIG_PATH="/opt/homebrew/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
  fi
  (cd "$linux" && cargo build --quiet -p unfold)
elif [ "$(uname -s)" != Darwin ] || [ ! -d ../unfold/.build/xcode/Build/Products/Debug/Unfold.app ]; then
  echo "no client is checked out beside this repo: the conformance tests have nothing to run"
  export UNFOLD_ALLOW_NO_CLIENTS=1
fi

bun test
