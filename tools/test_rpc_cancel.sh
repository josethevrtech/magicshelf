#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
mkdir -p build/tests
c++ -std=c++17 -O2 -pthread -Inative tests/rpc_cancel_test.cpp -o build/tests/rpc_cancel_test $(pkg-config --cflags --libs egl glesv2 cairo json-c)
timeout 10 build/tests/rpc_cancel_test
