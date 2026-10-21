#!/usr/bin/env python3
"""Export the SDK without the app, creation assets, backend code, or user data."""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(output):
    version = json.loads((ROOT / "sdk/version.json").read_text())
    paths = version["headers"] + ["sdk/version.json", "LICENSE", "OPENVR-LICENSE.txt",
        "tools/package_creation.py", "magicshelf/__init__.py", "magicshelf/contracts.py",
        "magicshelf/packages.py", "docs/MODULES.md", "docs/CREATING.md"]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'magicshelf-sdk-{version["sdk_version"]}.tar.gz'
    with tarfile.open(archive, "w:gz") as tar:
        for name in sorted(paths):
            tar.add(ROOT / name, arcname="magicshelf-sdk/" + name, recursive=False)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + ".sha256").write_text(f"{digest}  {archive.name}\n")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    print(build(parser.parse_args().output))
