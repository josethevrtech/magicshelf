#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
mkdir -p build/tests
c++ -std=c++17 -O2 -Inative tests/storefront_test.cpp -o build/tests/storefront_test $(pkg-config --cflags --libs egl glesv2 cairo json-c)
build/tests/storefront_test
