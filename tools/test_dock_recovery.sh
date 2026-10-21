#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT
for profile in pet phone; do
  flags=()
  if [[ "$profile" == phone ]]; then flags+=(-DANDROID_PHONE); fi
  c++ -O2 -std=c++17 -Inative "${flags[@]}" tests/dock_recovery_test.cpp \
    -o "$test_dir/$profile" $(pkg-config --cflags --libs egl glesv2 cairo json-c)
  "$test_dir/$profile"
done
