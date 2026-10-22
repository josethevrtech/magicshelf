#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
mkdir -p build/bin
arch="$(uname -m)"
case "$arch" in aarch64) vr=/opt/steamvr/bin/linuxarm64;; x86_64) vr=/opt/steamvr/bin/linux64;; *) echo 'Unsupported architecture' >&2; exit 1;; esac
flags=(-O2 -std=c++17 -pthread -Inative -L"$vr" -lopenvr_api -Wl,-rpath,"$vr")
c++ native/host.cpp -o build/bin/magicshelf-vr "${flags[@]}" $(pkg-config --cflags --libs egl glesv2 cairo json-c)
build/bin/magicshelf-vr --icon build/icon.png
python3 tools/build_release.py --architecture "$arch"
