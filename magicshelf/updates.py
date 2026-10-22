"""Subscription checks, verified download caching and non-disruptive updates."""
import errno
import contextlib
import os
import tempfile
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .contracts import catalog, load, machine, require, version


def update_error(error):
    if isinstance(error, urllib.error.HTTPError):
        if error.code == 404:
            return "This download is temporarily unavailable. Try again later."
        if error.code == 429:
            return "The download service is busy. MagicShelf will retry."
    if isinstance(error, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return "Could not connect. Check Wi-Fi or try again later."
    if isinstance(error, OSError) and error.errno == errno.ENOSPC:
        return "There is not enough storage. Free some space and try again."
    return str(error)[:180]


class Updates:
    def request_update_check(self):
        """Return immediately so a manual check does not lock the native controls."""
        import threading
        with self._request_lock:
            if self._sync_lock.locked() or (self._check_thread and self._check_thread.is_alive()):
                return self.snapshot()
            self.checking = True
            self.update_message = "Checking for updates. You can keep using your creations."
            self.publish()
            def run():
                try:
                    self.sync_subscriptions(manual=True)
                except Exception as error:
                    self.update_message = update_error(error)
                finally:
                    self.checking = False
                    self.publish()
            self._check_thread = threading.Thread(target=run, daemon=True)
            self._check_thread.start()
        return self.snapshot()

    def refresh(self):
        # Fetch independently: an unavailable publisher cannot block another.
        # Network work does not hold the action lock or disable collection controls.
        from .manager import download
        with self._refresh_lock:
            urls = list(self.state["catalogs"])
            self.checking = True
            self.publish()
            def fetch(url):
                try:
                    with tempfile.TemporaryDirectory(dir=self.root) as temp:
                        path = Path(temp) / "catalog.json"
                        download(url, path, 1024 * 1024)
                        return catalog(load(path))["modules"], None
                except Exception as error:
                    return None, update_error(error)
            try:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = dict(zip(urls, pool.map(fetch, urls)))
                with self.transaction():
                    cached = list(self.state["catalog"])
                    items, seen, failures = [], set(), {}
                    for url in self.state["catalogs"]:
                        entries, error = results.get(url, (None, "Waiting for the next check."))
                        if error:
                            failures[url] = error
                            entries = [i for i in cached if i.get("catalog_url") == url]
                        for item in entries:
                            key = item["id"]
                            owner = self.state["modules"].get(key, {}).get("catalog_url") or self.state["subscriptions"].get(key, {}).get("catalog_url")
                            if key not in seen and not self.is_adapter(key) and item["architecture"] == machine() and (not owner or owner == url):
                                items.append({**item, "catalog_url": url})
                                seen.add(key)
                    self.state["catalog"] = items
                    self.catalog_errors = failures
                    self.state["last_update_check"] = time.time()
                    self.save()
                    self.message = "Collection checked." if not failures else "Some downloads are offline. Your installed creations are available."
                # Preview downloads never delay creation updates or block controls.
                self.cache_previews(items)
            finally:
                self.checking = False
                self.publish()
        return self.snapshot()

    def cache_previews(self, items):
        from .storefront import cache_images
        import threading
        if not self._preview_lock.acquire(blocking=False):
            return
        def run():
            try:
                cache_images(items, self.root)
            finally:
                self._preview_lock.release()
        threading.Thread(target=run, daemon=True).start()

    def refresh_and_sync(self):
        return self.sync_subscriptions(manual=True)

    def download_path(self, key, item):
        return self.root / "downloads" / key / (item["version"] + "-" + item["sha256"] + ".magicshelf")

    def prune_downloads(self, key, keep=None):
        # Cache cleanup must not turn a successful installation into a failure.
        for path in (self.root / "downloads" / key).glob('*.magicshelf'):
            if path != keep:
                with contextlib.suppress(OSError):
                    path.unlink(missing_ok=True)

    def remember_update_error(self, key, item, error):
        old = self.state["update_errors"].get(key, {})
        attempts = old.get("attempts", 0) + 1 if old.get("version") == item["version"] else 1
        self.state["update_errors"][key] = {"version": item["version"], "message": update_error(error), "attempts": attempts,
                                            "retry_at": time.time() + min(900, 60 * 2 ** min(attempts - 1, 4))}
        self.save()

    def install_item(self, key, permissions, automatic=False, item=None):
        # Called only while holding the manager transaction lock.
        from .manager import download, unpack
        item = item or next((i for i in self.state["catalog"] if i["id"] == key), None)
        require(item is not None, "Creation is not in a followed collection")
        require(isinstance(permissions, list) and set(permissions) == set(item["permissions"]), "Review this creation's permissions before installing")
        from . import VERSION
        require(version(VERSION) >= version(item.get('minimum_framework_version', '0.0.0')), 'Update MagicShelf first, then download this creation. Choose Check updates in Settings.')
        old = self.state["modules"].get(key)
        require(not old or not old.get("catalog_url") or old["catalog_url"] == item["catalog_url"], "A different collection cannot replace this creation")
        require(not old or version(item["version"]) > version(old["version"]), "This version is already installed")
        self.transfer = dict(id=key, name=item["name"], stage="downloading", received_bytes=0, total_bytes=item["size_bytes"], active=True)
        last_publish = 0.
        def progress(received):
            nonlocal last_publish
            self.transfer = {**self.transfer, "received_bytes": received}
            now = time.monotonic()
            if now - last_publish >= .2 or received == item["size_bytes"]:
                self.publish()
                last_publish = now
        def stage(name, active=True, **extra):
            self.transfer = {**self.transfer, "stage": name, "active": active, **extra}
            self.publish()
        cached = self.download_path(key, item)
        try:
            with tempfile.TemporaryDirectory(dir=self.root) as temp:
                archive = Path(temp) / "module.magicshelf"
                if cached.is_file():
                    archive = cached
                else:
                    download(item["url"], archive, item["size_bytes"], progress=progress)
                require(archive.stat().st_size == item["size_bytes"], "Download was incomplete. Please try again.")
                stage("checking", received_bytes=item["size_bytes"])
                staged = Path(temp) / "unpacked"
                unpack(archive, staged, item["sha256"], item)
                if automatic and old and old["enabled"]:
                    if archive != cached:
                        cached.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(archive, cached)
                    self.state["pending_updates"][key] = dict(item)
                    self.state["update_errors"].pop(key, None)
                    self.save()
                    self.prune_downloads(key, keep=cached)
                    self.message = "Update downloaded. Turn this creation Off to install it."
                    stage("ready", active=False)
                    return False
                stage("installing")
                self.commit_package(key, item["version"], staged, item["catalog_url"])
                self.state["pending_updates"].pop(key, None)
                self.state["update_errors"].pop(key, None)
                self.state["held_updates"].pop(key, None)
                self.save()
                self.prune_downloads(key)
                stage("complete", active=False)
                return True
        except Exception as error:
            # Revalidate even cached downloads. A damaged cache must be replaceable.
            with contextlib.suppress(OSError):
                cached.unlink(missing_ok=True)
            self.state["pending_updates"].pop(key, None)
            self.remember_update_error(key, item, error)
            stage("failed", active=False, error=update_error(error))
            raise

    def apply_pending(self, key):
        item = self.state["pending_updates"].get(key)
        sub = self.state["subscriptions"].get(key)
        old = self.state["modules"].get(key)
        if not item or not sub or not old or old["enabled"]:
            return
        if version(item["version"]) <= version(old["version"]):
            self.state["pending_updates"].pop(key, None)
            self.save()
            return
        if sub["catalog_url"] != item["catalog_url"] or not set(item["permissions"]).issubset(sub["permissions"]):
            return
        try:
            self.install_item(key, item["permissions"], automatic=True, item=item)
        except Exception as error:
            self.message = "Turned Off. Your previous version is kept. " + update_error(error)

    def sync_subscriptions(self, refresh=True, manual=False):
        if not self._sync_lock.acquire(blocking=False):
            return self.snapshot()
        try:
            if refresh:
                self.refresh()
            updated, ready, reviews, failures = 0, 0, 0, 0
            for key in list(self.state["subscriptions"]):
                with self.transaction():
                    sub = self.state["subscriptions"].get(key)
                    if not sub:
                        continue
                    item = next((i for i in self.state["catalog"] if i["id"] == key and i.get("catalog_url") == sub["catalog_url"]), None)
                    installed = self.state["modules"].get(key)
                    if not item or (installed and version(item["version"]) <= version(installed["version"])):
                        if sub["catalog_url"] not in self.catalog_errors:
                            # A publisher may withdraw an update. Do not install
                            # its queued archive after a successful catalog check.
                            changed = False
                            for field in ("pending_updates", "update_errors"):
                                changed = self.state[field].pop(key, None) is not None or changed
                            if changed:
                                self.save()
                                self.prune_downloads(key)
                        continue
                    if self.state["held_updates"].get(key) == item["version"]:
                        continue
                    if not set(item["permissions"]).issubset(sub["permissions"]):
                        reviews += 1
                        continue
                    pending = self.state["pending_updates"].get(key)
                    if pending and pending["sha256"] == item["sha256"] and installed and installed["enabled"] and self.download_path(key, pending).is_file():
                        ready += 1
                        continue
                    error = self.state["update_errors"].get(key)
                    if not manual and error and error["version"] == item["version"] and time.time() < error["retry_at"]:
                        failures += 1
                        continue
                    try:
                        if self.install_item(key, item["permissions"], automatic=True):
                            updated += 1
                        else:
                            ready += 1
                    except Exception:
                        failures += 1
            messages = []
            if updated:
                messages.append(f"{updated} creation{'s' if updated != 1 else ''} updated.")
            if ready:
                messages.append("Updates are ready. Turn creations Off to install them.")
            if reviews:
                messages.append("An update needs a permissions review. Open its creation page.")
            if failures:
                messages.append("Some updates will retry. Your installed versions are kept.")
            if self.catalog_errors:
                messages.append("Some collections could not be checked. MagicShelf will retry.")
            if self.state["held_updates"]:
                messages.append("A restored version is kept until you choose an update or a newer one is released.")
            self.update_message = " ".join(messages) or ("Your subscriptions are up to date." if self.state["subscriptions"] else "Collection checked. Subscribe to receive automatic updates.")
            self.publish()
            return self.snapshot()
        finally:
            self._sync_lock.release()

    def update_status(self, key, item):
        candidate = item.get("update")
        pending = self.state["pending_updates"].get(key)
        error = self.state["update_errors"].get(key)
        sub = self.state["subscriptions"].get(key)
        if candidate and self.state["held_updates"].get(key) == candidate["version"]:
            return "held", "Previous version restored. This update waits for your approval."
        if candidate and sub and not set(candidate["permissions"]).issubset(sub["permissions"]):
            return "review", "This update needs your permission. Choose Review update in Settings."
        if error and (not candidate or error["version"] == candidate["version"]):
            return "failed", error["message"] + (" Your installed version is kept." if item.get("installed") else " Nothing was installed. Try Subscribe & download again.")
        if pending:
            return "ready", "Update downloaded. Turn this creation Off to install it, or choose Update now in Settings."
        if candidate:
            return "available", "An update is available. Open Settings to review it."
        return "current", "Updates download automatically and install while this creation is Off." if sub else ""
