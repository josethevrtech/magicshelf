"""Transactional module storage, user services, and the single shelf layout."""
import contextlib
import fcntl
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from . import VERSION
from .contracts import ContractError, MAX_MODULES, catalog, load, machine, require, version
from .packages import download, unpack
from .storefront import cache_images, decorate
from . import preferences

OFFICIAL = "https://raw.githubusercontent.com/josethevrtech/magicshelf/main/catalog.json"
ADAPTERS = {
    "org.magicshelf.android-phone": {"name": "Android Phone", "description": "Your Android phone. Off pauses Android and its audio; On resumes your apps.", "overlay": "local.androidphone.device", "shell": "android-phone-vr.service", "backends": ["digitalpartner-android.service", "android-phone-bridge.service"], "binary": "android-phone-vr", "container": "lepton-courage-tablet"},
    "org.magicshelf.digital-partner": {"name": "Digivice", "description": "Your Digital Partner. Off pauses the game and its audio; On resumes your pet.", "overlay": "local.digitalpartner.device", "shell": "digitalpartner-vr.service", "backends": ["digitalpartner.service"], "binary": "digitalpartner-vr"},
}

def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
        temp = Path(f.name)
        try:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
            temp.chmod(0o600)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

def quote(value):
    # systemd syntax, not shell syntax; suppress specifier and environment expansion.
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$").replace("\n", "\\n") + '"'

class System:
    def call(self, *args, check=True):
        return subprocess.run(["systemctl", "--user", *args], check=check, text=True, capture_output=True, timeout=70)

    def active(self, unit):
        return self.call("is-active", "--quiet", unit, check=False).returncode == 0

    def pause_container(self, name, paused):
        # Lepton's Android processes live in a separate Podman scope, outside
        # the gamescope service. Freeze that exact container as well.
        result = subprocess.run(["podman", "ps", "--all", "--filter", "name=^" + name + "$", "--format", "json"],
                                check=True, text=True, capture_output=True, timeout=15)
        for item in json.loads(result.stdout):
            if name not in item.get("Names", []):
                continue
            require(item.get("Labels", {}).get("lepton") == "true", "Android container does not belong to Lepton")
            expected = "running" if paused else "paused"
            if item["State"] == expected:
                subprocess.run(["podman", "pause" if paused else "unpause", item["Id"]],
                               check=True, text=True, capture_output=True, timeout=15)

class Manager:
    def __init__(self, home=None, runtime=None, system=None):
        self.home = Path(home or Path.home())
        self.root = self.home / ".local/share/magicshelf"
        self.config = self.home / ".config/magicshelf"
        self.units = self.home / ".config/systemd/user"
        self.runtime = Path(runtime or Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/" + str(os.getuid()))) / "magicshelf")
        for p in (self.root, self.config, self.units, self.runtime):
            p.mkdir(parents=True, exist_ok=True)
        self.runtime.chmod(0o700)
        self.system = system or System()
        self.legacy = self.home / "Applications/DigitalPartner/vr"
        self.statepath = self.config / "state.json"
        seed = Path(__file__).resolve().parent.parent / "catalog.json"
        collections = seed.with_name('collections.json')
        default_catalogs = [OFFICIAL]
        if collections.exists():
            from .packages import check_url
            defaults = load(collections)
            require(defaults.get('schema_version') == 1, 'Unsupported collections schema')
            default_catalogs += [check_url(url) for url in defaults['catalogs']]
        initial = [{**i, "catalog_url": OFFICIAL} for i in catalog(load(seed))["modules"] if i["architecture"] == machine()] if seed.exists() else []
        self.state = load(self.statepath) if self.statepath.exists() else {"schema_version": 1, "modules": {}, "catalogs": default_catalogs, "catalog": initial}
        require(self.state.get("schema_version") == 1 and isinstance(self.state.get("modules"), dict), "Unsupported MagicShelf state; restore the backup before continuing")
        self.layoutpath = self.config / "object-dock.json"
        if not self.layoutpath.exists():
            source = self.legacy / "object-dock.json"
            atomic(self.layoutpath, load(source) if source.exists() else load(Path(__file__).parent.parent / "shelf.json"))
        self.sessionpath = self.config / "sessions.json"
        self.sessions = load(self.sessionpath) if self.sessionpath.exists() else {}
        self.ready = set()
        self.state.setdefault("subscriptions", {})
        self.update_message = "Subscriptions check for updates automatically."
        self.message = "Ready"
        self.busy = False
        self.transfer = None
        self.publish()

    @contextlib.contextmanager
    def transaction(self):
        with (self.config / "transaction.lock").open("a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            self.busy = True
            try:
                yield
            finally:
                self.busy = False
                self.publish()

    def save(self):
        require(sum(bool(v.get("enabled")) for v in self.state["modules"].values()) <= MAX_MODULES, "The shelf supports up to 16 enabled creations")
        atomic(self.statepath, self.state)
        self.layout()

    def layout(self):
        data = load(self.layoutpath)
        data["objects"] = [ADAPTERS[k]["overlay"] if self.is_adapter(k) else "magicshelf.module." + k for k, v in self.state["modules"].items() if v.get("enabled")]
        require(len(data["objects"]) <= MAX_MODULES, "The shelf supports up to 16 enabled creations")
        atomic(self.layoutpath, data)

    def adopt(self):
        marker = self.legacy / "magicshelf-api-version"
        require(marker.is_file() and marker.read_text().strip() in ("1", "2"), "Migrate the local device shells before adding them to MagicShelf")
        with self.transaction():
            for key, item in ADAPTERS.items():
                if (self.legacy / item["binary"]).is_file() and key not in self.state["modules"]:
                    room = sum(bool(i.get("enabled")) for i in self.state["modules"].values()) < MAX_MODULES
                    self.state["modules"][key] = {"adapter": True, "version": "0.1.0", "enabled": room}
            self.save()
            self.message = "Existing devices added; their app data stays in place."
        return self.snapshot()

    def is_adapter(self, key):
        return key in ADAPTERS and bool(self.state['modules'].get(key, {}).get('adapter'))

    def unit(self, key):
        return ADAPTERS[key]["shell"] if self.is_adapter(key) else "magicshelf-module-" + key + ".service"

    def modulepath(self, key, ver):
        return self.root / "modules" / key / "versions" / ver

    def metadata(self, key, state):
        if self.is_adapter(key):
            return {**ADAPTERS[key], "id": key, "version": state["version"], "permissions": ["vr-overlay"], "license": "Existing local installation", "architecture": machine()}
        return load(self.modulepath(key, state["version"]) / "module.json")

    def write_unit(self, key):
        state = self.state["modules"][key]
        if self.is_adapter(key):
            return
        meta = self.metadata(key, state)
        directory = self.modulepath(key, state["version"])
        data = self.root / "module-data" / key
        data.mkdir(parents=True, exist_ok=True)
        session = secrets.token_hex(24)
        self.sessions[key] = session
        atomic(self.sessionpath, self.sessions)
        self.ready.discard(key)
        env = {"MAGICSHELF_API_VERSION": str(meta["api_version"]), "MAGICSHELF_MODULE_ID": key, "MAGICSHELF_MODULE_KEY": "magicshelf.module." + key, "MAGICSHELF_SESSION": session, "MAGICSHELF_DATA_DIR": str(data), "MAGICSHELF_RUNTIME_DIR": str(self.runtime), "MAGICSHELF_LAYOUT_DIR": str(self.config), "MAGICSHELF_SHELF_OWNER": "0"}
        if meta['api_version'] == 2:
            backend_data = self.root / 'runtime-data' / key
            cache = self.home / '.cache/magicshelf' / key
            backend_data.mkdir(parents=True, exist_ok=True)
            cache.mkdir(parents=True, exist_ok=True)
            env.update(MAGICSHELF_BACKEND_DATA_DIR=str(backend_data), MAGICSHELF_CACHE_DIR=str(cache))
        lines = ["[Unit]", "Description=MagicShelf module " + key, "BindsTo=steamvr.service", "After=steamvr.service magicshelf.service", "PartOf=steamvr.service", "StartLimitIntervalSec=60", "StartLimitBurst=3", "", "[Service]", "Type=simple", "ExecStart=" + quote(directory / meta["entrypoint"]), "WorkingDirectory=" + str(directory).replace("%", "%%"), "Restart=on-failure", "RestartSec=5", "TimeoutStopSec=45", "NoNewPrivileges=" + ("no" if "external-runtime" in meta["permissions"] else "yes"), "UMask=0077", "MemoryMax=" + str(meta.get("memory_mb", 256)) + "M", "MemorySwapMax=64M", "Nice=5"]
        if meta.get('cleanup_entrypoint'):
            lines += ['ExecStopPost=' + quote(directory / meta['cleanup_entrypoint'])]
        lines += ["Environment=" + quote(k + "=" + v) for k, v in env.items()]
        lines += ["", "[Install]", "WantedBy=steamvr.service", ""]
        (self.units / self.unit(key)).write_text("\n".join(lines))
        (self.units / self.unit(key)).chmod(0o600)
        self.system.call("daemon-reload")

    def start(self, key):
        item = self.state["modules"][key]
        self.write_unit(key)
        self.system.call("enable", self.unit(key))
        if not self.system.active("steamvr.service"):
            return  # Enabled for the next normal SteamVR start.
        if self.is_adapter(key):
            self.resume_adapter(key)
            self.system.call("start", *ADAPTERS[key]["backends"])
        self.system.call("reset-failed", self.unit(key), check=False)
        self.system.call("start", self.unit(key))
        until = time.monotonic() + self.metadata(key, item).get("startup_timeout_sec", 20)
        while time.monotonic() < until:
            if self.is_adapter(key):
                result = subprocess.run([str(self.legacy / ADAPTERS[key]["binary"]), "--status"], timeout=3, capture_output=True)
                if result.returncode == 0:
                    subprocess.run([str(self.legacy / ADAPTERS[key]["binary"]), "--dock"], timeout=3, check=True)
                    return
            elif key in self.ready and self.system.active(self.unit(key)):
                return
            time.sleep(.25)
        raise ContractError("Creation did not become ready; its previous version has been restored")

    def pause_adapter(self, key):
        marker = self.legacy / "magicshelf-api-version"
        require(marker.is_file() and marker.read_text().strip() == "2",
                "Update the local device shells before hiding devices; this preserves their live display connection")
        if self.system.active(self.unit(key)):
            subprocess.run([str(self.legacy / ADAPTERS[key]["binary"]), "--hide"], timeout=3, check=True)
        # Keep the capture consumer connected: disconnecting it can permanently
        # lose gamescope's source. Suspend the producers instead. Also remove
        # their independent SteamVR autostart links, not just the shell's link.
        self.system.call("disable", self.unit(key), *ADAPTERS[key]["backends"])
        for unit in ADAPTERS[key]["backends"]:
            if self.system.active(unit):
                self.system.call("freeze", unit)
        if "container" in ADAPTERS[key]:
            self.system.pause_container(ADAPTERS[key]["container"], True)

    def resume_adapter(self, key):
        # Make Android available before its bridge can issue container commands.
        if "container" in ADAPTERS[key]:
            self.system.pause_container(ADAPTERS[key]["container"], False)
        for unit in ADAPTERS[key]["backends"]:
            if self.system.active(unit):
                self.system.call("thaw", unit)

    def enable_adapter(self, key):
        if not self.system.active(self.unit(key)):
            self.start(key)
        else:
            self.system.call("enable", self.unit(key))
            self.resume_adapter(key)
            self.system.call("start", *ADAPTERS[key]["backends"])
            subprocess.run([str(self.legacy / ADAPTERS[key]["binary"]), "--dock"], timeout=3, check=True)

    def toggle(self, key, enabled):
        require(type(enabled) is bool, "enabled must be true or false")
        require(key in self.state["modules"], "Creation is not installed")
        with self.transaction():
            old = self.state["modules"][key]["enabled"]
            require(not enabled or old or sum(bool(i["enabled"]) for i in self.state["modules"].values()) < MAX_MODULES, "The shelf is full")
            self.state["modules"][key]["enabled"] = enabled
            self.save()
            try:
                if enabled:
                    if self.is_adapter(key):
                        self.enable_adapter(key)
                    elif not self.system.active(self.unit(key)):
                        self.start(key)
                elif self.is_adapter(key):
                    self.pause_adapter(key)
                else:
                    self.system.call("disable", "--now", self.unit(key), check=False)
            except Exception:
                self.state["modules"][key]["enabled"] = old
                self.save()
                if self.is_adapter(key):
                    if old:
                        self.enable_adapter(key)
                    else:
                        self.pause_adapter(key)
                elif not old:
                    self.system.call("disable", "--now", self.unit(key), check=False)
                raise
            self.message = ("Enabled " if enabled else "Turned off ") + self.metadata(key, self.state["modules"][key])["name"]
        return self.snapshot()

    def control(self, key, command):
        if self.is_adapter(key):
            executable = self.legacy / ADAPTERS[key]['binary']
        else:
            meta = self.metadata(key, self.state['modules'][key])
            require(meta.get('control_entrypoint'), 'This creation has no on-device controls')
            executable = self.modulepath(key, meta['version']) / meta['control_entrypoint']
        env = {**os.environ, 'MAGICSHELF_DATA_DIR': str(self.root / 'module-data' / key)}
        subprocess.run([str(executable), command], env=env, timeout=5, check=True)

    def open(self, key):
        require(key in self.state['modules'], 'Creation is not installed')
        self.toggle(key, True)
        self.control(key, '--show')
        self.message = 'Opened ' + self.metadata(key, self.state['modules'][key])['name']
        return self.snapshot()

    def add_catalog(self, url):
        from .packages import check_url
        check_url(url)
        with self.transaction():
            # Check the subscription before recording it.
            with tempfile.TemporaryDirectory(dir=self.root) as temp:
                path = Path(temp) / "catalog.json"
                download(url, path, 1024 * 1024)
                catalog(load(path))
            if url not in self.state["catalogs"]:
                self.state["catalogs"].append(url)
                self.save()
        return self.refresh()

    def refresh(self):
        with self.transaction():
            items = []
            seen = set()
            for url in self.state["catalogs"]:
                with tempfile.TemporaryDirectory(dir=self.root) as temp:
                    path = Path(temp) / "catalog.json"
                    download(url, path, 1024 * 1024)
                    data = catalog(load(path))
                for item in data["modules"]:
                    if item["id"] not in seen and not self.is_adapter(item["id"]) and item["architecture"] == machine():
                        items.append({**item, "catalog_url": url})
                        seen.add(item["id"])
            self.state["catalog"] = items
            self.save()
            self.message = "Collection updated"
        cache_images(items, self.root)
        return self.snapshot()

    def install(self, key, permissions):
        with self.transaction():
            self.install_item(key, permissions)
        return self.snapshot()

    def refresh_and_sync(self):
        self.refresh()
        return self.sync_subscriptions(refresh=False)

    def install_item(self, key, permissions):
        # Called only while holding the manager transaction lock.
        item = next((i for i in self.state["catalog"] if i["id"] == key), None)
        require(item is not None, "Creation is not in a followed collection")
        require(isinstance(permissions, list) and set(permissions) == set(item["permissions"]), "Review this creation's permissions before installing")
        old = self.state["modules"].get(key)
        require(not old or not old.get("catalog_url") or old["catalog_url"] == item["catalog_url"], "A different collection cannot replace this creation")
        self.transfer = dict(id=key, name=item['name'], stage='downloading', received_bytes=0, total_bytes=item['size_bytes'], active=True)
        last_publish = 0.
        def progress(received):
            nonlocal last_publish
            self.transfer = {**self.transfer, 'received_bytes': received}
            now = time.monotonic()
            if now - last_publish >= .2 or received == item['size_bytes']:
                self.publish()
                last_publish = now
        def stage(name, active=True, **extra):
            self.transfer = {**self.transfer, 'stage': name, 'active': active, **extra}
            self.publish()
        try:
            with tempfile.TemporaryDirectory(dir=self.root) as temp:
                archive = Path(temp) / "module.magicshelf"
                download(item["url"], archive, item["size_bytes"], progress=progress)
                require(archive.stat().st_size == item["size_bytes"], "Package size differs from catalog")
                stage('checking', received_bytes=item['size_bytes'])
                staged = Path(temp) / "unpacked"
                unpack(archive, staged, item["sha256"], item)
                stage('installing')
                self.commit_package(key, item["version"], staged, item["catalog_url"])
                stage('complete', active=False)
                return self.snapshot()
        except Exception as error:
            stage('failed', active=False, error=str(error)[:180])
            raise

    def subscribe(self, key, subscribed, permissions=None):
        require(type(subscribed) is bool, "subscribed must be true or false")
        with self.transaction():
            if not subscribed:
                self.state["subscriptions"].pop(key, None)
                self.save()
                self.message = "Unsubscribed. Your installed creation and saves are kept."
            else:
                require(not self.is_adapter(key), "This local installation has no downloadable package yet")
                item = next((i for i in self.state["catalog"] if i["id"] == key), None)
                require(item is not None, "Creation is not available for download")
                require(isinstance(permissions, list) and set(permissions) == set(item["permissions"]), "Review this creation's permissions before subscribing")
                old = self.state["modules"].get(key)
                require(not old or not old.get("catalog_url") or old["catalog_url"] == item["catalog_url"], "A different collection cannot replace this creation")
                if not old or version(item["version"]) > version(old["version"]):
                    self.install_item(key, permissions)
                self.state["subscriptions"][key] = {"catalog_url": item["catalog_url"], "permissions": list(permissions)}
                self.save()
                self.message = "Installed and subscribed. Future updates install automatically."
        return self.snapshot()

    def sync_subscriptions(self, refresh=True):
        if refresh:
            try:
                self.refresh()
            except Exception as error:
                self.update_message = "Updates will retry: " + str(error)[:180]
                return self.snapshot()
        if not self.state["subscriptions"]:
            self.update_message = "Collection checked. Subscribe to receive automatic updates."
            return self.snapshot()
        failures, updated = [], 0
        for key in list(self.state["subscriptions"]):
            with self.transaction():
                sub = self.state["subscriptions"].get(key)
                if not sub:  # An unsubscribe while checking cancels this update.
                    continue
                item = next((i for i in self.state["catalog"] if i["id"] == key and i.get("catalog_url") == sub["catalog_url"]), None)
                installed = self.state["modules"].get(key)
                if not item or (installed and version(item["version"]) <= version(installed["version"])):
                    continue
                if not set(item["permissions"]).issubset(sub["permissions"]):
                    failures.append(item["name"] + " needs a permissions review")
                    continue
                try:
                    self.install_item(key, item["permissions"])
                    updated += 1
                except Exception as error:
                    failures.append(item["name"] + ": " + str(error)[:140])
        self.update_message = "; ".join(failures) if failures else (str(updated) + " creation(s) updated." if updated else "Your subscriptions are up to date.")
        self.publish()
        return self.snapshot()

    def open_link(self, key, index):
        from .contracts import external_url
        item = next((m for m in self.snapshot()["modules"] if m["id"] == key), None)
        require(item is not None and type(index) is int, "Unknown creation link")
        links = list(item.get("links", []))
        for credit in item.get("credits", []):
            for field in ("url", "support_url"):
                if credit.get(field):
                    links.append({"url": credit[field]})
        require(0 <= index < len(links), "Unknown creation link")
        subprocess.run(["xdg-open", external_url(links[index]["url"])], check=True, timeout=10, capture_output=True)
        self.message = "Link opened in your browser."
        return self.snapshot()

    def commit_package(self, key, ver, staged, source=None):
        from copy import deepcopy
        old = deepcopy(self.state["modules"].get(key))
        if old:
            require(not old.get("adapter"), "Local adapters cannot be overwritten by downloads")
            require(version(ver) > version(old["version"]), "Install must be a newer version")
        target = self.modulepath(key, ver)
        require(not target.exists(), "That version already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, target)
        enabled = bool(old and old["enabled"])
        data = self.root / "module-data" / key
        checkpoint = self.root / "data-backups" / key / str(time.time_ns())
        checkpoint_ready = False
        try:
            if enabled:
                self.system.call("stop", self.unit(key))
            if old and data.exists():
                checkpoint.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(data, checkpoint, symlinks=True)
                checkpoint_ready = True
            self.state["modules"][key] = {"version": ver, "enabled": enabled, "previous_version": old["version"] if old else None, "previous_data": str(checkpoint) if checkpoint.exists() else None, "catalog_url": source}
            self.save()
            if enabled:
                self.start(key)
            self.message = "Installed " + self.metadata(key, self.state["modules"][key])["name"]
            return self.snapshot()
        except Exception:
            self.system.call("stop", self.unit(key), check=False)
            if checkpoint_ready:
                if data.exists():
                    data.rename(data.with_name(key + ".failed-" + str(time.time_ns())))
                checkpoint.rename(data)
            if old:
                self.state["modules"][key] = old
            else:
                self.state["modules"].pop(key, None)
            self.save()
            try:
                if old and enabled:
                    self.start(key)
            finally:
                shutil.rmtree(target)
            raise

    def bootstrap(self):
        release = Path(__file__).resolve().parent.parent
        info = load(release / "release.json")
        with self.transaction():
            for item in info.get("bundled", []):
                old = self.state["modules"].get(item["id"])
                if old and version(old["version"]) >= version(item["version"]):
                    continue
                with tempfile.TemporaryDirectory(dir=self.root) as temp:
                    staged = Path(temp) / "unpacked"
                    meta = unpack(release / item["path"], staged, item["sha256"])
                    require(meta["id"] == item["id"] and meta["version"] == item["version"], "Bundled module mismatch")
                    self.commit_package(meta["id"], meta["version"], staged, OFFICIAL)
        return self.snapshot()

    def reconcile(self):
        # Repair interrupted toggles without restarting healthy creations or backends.
        with self.transaction():
            self.layout()
            for key, item in list(self.state["modules"].items()):
                try:
                    if item["enabled"]:
                        if not self.system.active(self.unit(key)):
                            self.start(key)
                        elif self.is_adapter(key):
                            self.system.call("enable", self.unit(key))
                            self.resume_adapter(key)
                            self.system.call("start", *ADAPTERS[key]["backends"])
                    elif self.is_adapter(key):
                        self.pause_adapter(key)
                    else:
                        self.system.call("disable", "--now", self.unit(key), check=False)
                except Exception as e:
                    self.message = "Could not apply saved state for " + key + ": " + str(e)

    def rollback(self, key):
        require(key in self.state["modules"] and not self.is_adapter(key), "Only packaged creations support version rollback")
        old = dict(self.state["modules"][key])
        previous = old.get("previous_version")
        require(previous and self.modulepath(key, previous).is_dir(), "No previous version is available")
        data = self.root / "module-data" / key
        archived = self.root / "data-backups" / key / ("before-rollback-" + str(time.time_ns()))
        with self.transaction():
            if old["enabled"]:
                self.system.call("stop", self.unit(key))
            if data.exists():
                archived.parent.mkdir(parents=True, exist_ok=True)
                data.rename(archived)
            checkpoint = Path(old["previous_data"]) if old.get("previous_data") else None
            try:
                if checkpoint and checkpoint.exists():
                    shutil.copytree(checkpoint, data, symlinks=True)
                self.state["modules"][key] = {**old, "version": previous, "previous_version": old["version"], "previous_data": str(archived) if archived.exists() else None}
                self.save()
                if old["enabled"]:
                    self.start(key)
                self.message = "Restored previous creation version and its saved data"
            except Exception:
                self.system.call("stop", self.unit(key), check=False)
                if data.exists():
                    data.rename(data.with_name(key + ".failed-rollback-" + str(time.time_ns())))
                if archived.exists():
                    archived.rename(data)
                self.state["modules"][key] = old
                self.save()
                if old["enabled"]:
                    self.start(key)
                raise
        return self.snapshot()

    def remove(self, key):
        require(key in self.state["modules"], "Creation is not installed")
        require(not self.is_adapter(key), "Local devices can be turned off; MagicShelf does not delete their existing installations")
        with self.transaction():
            self.system.call("disable", "--now", self.unit(key), check=False)
            self.state["modules"].pop(key)
            self.state["subscriptions"].pop(key, None)
            self.save()
            (self.units / self.unit(key)).unlink(missing_ok=True)
            self.system.call("daemon-reload")
            shutil.rmtree(self.root / "modules" / key)
            if self.transfer and self.transfer['id'] == key:
                self.transfer = None
            self.message = "Creation removed; its saved data is kept"
        return self.snapshot()

    def home_all(self):
        for key, state in list(self.state["modules"].items()):
            if state["enabled"] and self.system.active(self.unit(key)):
                if self.is_adapter(key) or self.metadata(key, state).get("control_entrypoint"):
                    self.control(key, "--dock")
        # New modules read their own home-generation counter through the SDK.
        data = {"api_version": 1, "generation": time.time_ns()}
        atomic(self.runtime / "home.json", data)
        self.message = "Returned creations home"
        return self.snapshot()

    def update_settings(self, changes):
        changes = preferences.validate(changes)
        with self.transaction():
            data = load(self.layoutpath)
            reposition = any(key in preferences.PLACEMENT_KEYS and data.get(key) != value for key, value in changes.items())
            data.update(changes)
            atomic(self.layoutpath, data)
            if reposition:
                self.home_all()
            self.message = "Settings saved." + (" Creations returned to the dock." if reposition else "")
        return self.snapshot()

    def reset_settings(self, group):
        require(group in ("shelf", "placement", "app"), "Unknown settings section")
        defaults = preferences.defaults()
        with self.transaction():
            data = load(self.layoutpath)
            data.update({c["key"]: defaults[c["key"]] for c in preferences.CONTROLS if c["group"] == group})
            atomic(self.layoutpath, data)
            if group != "app":
                self.home_all()
            self.message = "Default settings restored." + (" Creations returned to the dock." if group != "app" else "")
        return self.snapshot()

    def app_link(self, index):
        require(type(index) is int and 0 <= index < len(preferences.CREDITS), "Unknown app credit")
        subprocess.run(["xdg-open", preferences.CREDITS[index]["url"]], check=True, timeout=10, capture_output=True)
        self.message = "Link opened in your browser."
        return self.snapshot()

    def snapshot(self):
        modules = []
        for key, state in list(self.state["modules"].items()):
            try:
                meta = self.metadata(key, state)
                running = self.system.active(self.unit(key)) and (state["enabled"] or not self.is_adapter(key))
                modules.append({**meta, "installed": True, "enabled": state["enabled"], "running": running, "adapter": self.is_adapter(key), "can_configure": self.is_adapter(key) or bool(meta.get("control_entrypoint")), "previous_version": state.get("previous_version")})
            except (OSError, ValueError):
                modules.append({"id": key, "name": key, "version": state["version"], "description": "Module files are missing; restore or remove this creation.", "installed": True, "enabled": False, "running": False, "broken": True})
        installed = {i["id"]: i for i in modules}
        for item in self.state["catalog"]:
            if item["id"] not in installed:
                modules.append({**item, "installed": False, "enabled": False})
            elif version(item["version"]) > version(installed[item["id"]]["version"]):
                installed[item["id"]]["update"] = item
        modules = [decorate(item, self.root) for item in modules]
        for item in modules:
            sub = self.state["subscriptions"].get(item["id"])
            item["subscribed"] = bool(sub)
            item["subscription_available"] = not self.is_adapter(item["id"]) and any(i["id"] == item["id"] for i in self.state["catalog"])
            item["update_mode"] = "local" if self.is_adapter(item["id"]) else "automatic" if sub else "manual"
        return {"api_version": 1, "version": VERSION, "modules": modules, "catalogs": self.state["catalogs"], "preferences": preferences.snapshot(load(self.layoutpath)), "transfer": self.transfer, "busy": self.busy, "message": self.message, "update_message": self.update_message}

    def publish(self):
        atomic(self.runtime / "ui-state.json", self.snapshot())
