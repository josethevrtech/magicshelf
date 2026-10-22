"""Bounded downloads and extraction; downloaded packages have no install hooks."""
import hashlib
import os
import stat
import time
import http.client
import urllib.error
import urllib.request
import urllib.parse
import zipfile
from pathlib import Path
from .contracts import ContractError, manifest, relative, require, MAX_PACKAGE_BYTES, MAX_EXPANDED_BYTES

MAX_BYTES = MAX_PACKAGE_BYTES
HOSTS = {"github.com", "raw.githubusercontent.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com", "github-releases.githubusercontent.com"}

def check_url(url):
    p = urllib.parse.urlsplit(url)
    require(p.scheme == "https" and p.hostname in HOSTS and not p.username and not p.password and p.port in (None, 443), "Use an HTTPS GitHub release or catalog URL")
    return url

class GithubRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def download(url, path, limit=MAX_BYTES, progress=None):
    check_url(url)
    path = Path(path)
    # Never remove a file supplied by the caller. Each retry owns only the
    # incomplete file it created; verification still happens after downloading.
    if path.exists():
        raise FileExistsError(path)
    opener = urllib.request.build_opener(GithubRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": "MagicShelf/0.1", "Accept": "application/octet-stream"})
    deadline = time.monotonic() + max(120, min(1800, limit / (256 * 1024)))
    for attempt in range(3):
        count, created = 0, False
        if progress:
            progress(0)
        try:
            with opener.open(request, timeout=30) as response:
                check_url(response.geturl())
                headers = getattr(response, 'headers', None)
                expected = int(headers.get('Content-Length', 0)) if headers else 0
                require(expected <= limit, "Download exceeds its declared limit")
                with open(path, "xb") as output:
                    created = True
                    while chunk := response.read(65536):
                        count += len(chunk)
                        require(count <= limit, "Download exceeds its declared limit")
                        if time.monotonic() > deadline:
                            raise TimeoutError("Download timed out")
                        output.write(chunk)
                        if progress:
                            progress(count)
                    if expected and count != expected:
                        raise http.client.IncompleteRead(b'', max(0, expected-count))
                    output.flush()
                    os.fsync(output.fileno())
            return count
        except Exception as error:
            if created:
                path.unlink(missing_ok=True)
            transient = isinstance(error, (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead))
            if isinstance(error, urllib.error.HTTPError):
                transient = error.code in (408, 429, 500, 502, 503, 504)
                error.close()
            if not transient or attempt == 2 or time.monotonic() >= deadline:
                raise
            time.sleep(2 ** attempt)

def unpack(archive, destination, expected_hash, expected=None):
    require(archive.stat().st_size <= MAX_BYTES, "Package is too large")
    with archive.open("rb") as source:
        require(hashlib.file_digest(source, "sha256").hexdigest() == expected_hash, "Package checksum mismatch")
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        require(len(z.infolist()) <= 4096, "Too many package entries")
        require(sum(i.file_size for i in z.infolist()) <= MAX_EXPANDED_BYTES, "Expanded package is too large")
        seen = set()
        for info in z.infolist():
            name = info.filename.rstrip("/")
            relative(name)
            require(name not in seen, "Duplicate package path")
            seen.add(name)
            mode = info.external_attr >> 16
            require(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR), "Links and special files are not allowed")
            require(not info.flag_bits & 1, "Encrypted packages are not supported")
        require("module.json" in seen, "Package needs module.json at its root")
        require(z.getinfo("module.json").file_size <= 65536, "Module manifest is too large")
        import json
        meta = manifest(json.loads(z.read("module.json")))
        if expected:
            for key in ("id", "version", "api_version", "entrypoint", "architecture", "permissions", "memory_mb", "control_entrypoint", "cleanup_entrypoint", "startup_timeout_sec", "steam_requirements", "minimum_framework_version"):
                require(meta.get(key) == expected.get(key), "Package does not match its catalog: " + key)
        for info in z.infolist():
            target = destination / info.filename
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as source, target.open("xb") as output:
                    import shutil
                    shutil.copyfileobj(source, output)
                target.chmod(0o755 if (info.external_attr >> 16) & 0o111 else 0o644)
        entry = destination / meta["entrypoint"]
        require(entry.is_file() and os.access(entry, os.X_OK), "Module entrypoint is not executable")
    for field in ('control_entrypoint', 'cleanup_entrypoint'):
        if field in meta:
            helper = destination / meta[field]
            require(helper.is_file() and os.access(helper, os.X_OK), 'Lifecycle entrypoint is not executable')
    return meta
