#!/usr/bin/env python3
"""Package one independently versioned creation using the host's v1 validator."""
import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from magicshelf.contracts import catalog, load, manifest, relative, require
from magicshelf.packages import MAX_BYTES, unpack


def build(source, output, repository):
    source, output = Path(source).resolve(), Path(output).resolve()
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository), "Use owner/repository")
    require(output != source and source not in output.parents, "Output must be outside the package directory")
    meta = manifest(load(source / "module.json"))
    paths = sorted(source.rglob("*"))
    require(paths and len(paths) <= 4096, "Too many package entries")
    for path in paths:
        relative(path.relative_to(source).as_posix())
        mode = path.lstat().st_mode
        require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), "Links and special files are not allowed")
    files = [p for p in paths if p.is_file()]
    require(sum(p.stat().st_size for p in files) <= MAX_BYTES * 4, "Expanded package is too large")
    entry = source / meta["entrypoint"]
    require(entry.is_file() and os.access(entry, os.X_OK), "Entrypoint must be executable")
    require((source / "LICENSE").is_file(), "Include a LICENSE describing the packaged content")
    output.mkdir(parents=True, exist_ok=True)
    name = f'{meta["id"]}-{meta["version"]}-linux-{meta["architecture"]}.magicshelf'
    destination = output / name
    # Validate the exact bytes through the same reader used for installation.
    # Never overwrite an immutable version with different content.
    with tempfile.TemporaryDirectory(dir=output) as temp:
        archive = Path(temp) / name
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for path in files:
                info = zipfile.ZipInfo(path.relative_to(source).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                info.external_attr = (0o100755 if path.stat().st_mode & 0o111 else 0o100644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, path.read_bytes())
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        unpack(archive, Path(temp) / "verify", digest, meta)
        if destination.exists():
            require(hashlib.sha256(destination.read_bytes()).hexdigest() == digest,
                    "This version already exists with different bytes; bump the creation version")
        else:
            archive.replace(destination)
    item = {**meta, "url": f'https://github.com/{repository}/releases/download/v{meta["version"]}/{name}',
            "sha256": digest, "size_bytes": destination.stat().st_size}
    result = catalog({"schema_version": 1, "name": meta["name"], "modules": [item]})
    (output / "catalog.json").write_text(json.dumps(result, indent=2) + "\n")
    (output / "SHA256SUMS").write_text(f"{digest}  {name}\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Staged package directory, not the repository root")
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.repository), indent=2))
