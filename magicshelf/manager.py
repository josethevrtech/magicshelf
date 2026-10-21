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

OFFICIAL = "https://raw.githubusercontent.com/josethevrtech/magicshelf/main/catalog.json"
ADAPTERS = {
    "org.magicshelf.android-phone": {"name": "Android Phone", "description": "Your existing Android phone. Turning it off hides the device; Android keeps its apps running.", "overlay": "local.androidphone.device", "shell": "android-phone-vr.service", "backends": ["digitalpartner-android.service", "android-phone-bridge.service"], "binary": "android-phone-vr"},
    "org.magicshelf.digital-partner": {"name": "Digivice", "description": "Your existing Digital Partner. Turning it off hides the device; your pet keeps running.", "overlay": "local.digitalpartner.device", "shell": "digitalpartner-vr.service", "backends": ["digitalpartner.service"], "binary": "digitalpartner-vr"},
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
        return subprocess.run(["systemctl", "--user", *args], check=check, text=True, capture_output=True, timeout=45)

    def active(self, unit):
        return self.call("is-active", "--quiet", unit, check=False).returncode == 0

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
        initial = [{**i, "catalog_url": OFFICIAL} for i in catalog(load(seed))["modules"] if i["architecture"] == machine()] if seed.exists() else []
        self.state = load(self.statepath) if self.statepath.exists() else {"schema_version": 1, "modules": {}, "catalogs": [OFFICIAL], "catalog": initial}
        require(self.state.get("schema_version") == 1 and isinstance(self.state.get("modules"), dict), "Unsupported MagicShelf state; restore the backup before continuing")
        self.layoutpath = self.config / "object-dock.json"
        if not self.layoutpath.exists():
            source = self.legacy / "object-dock.json"
            atomic(self.layoutpath, load(source) if source.exists() else load(Path(__file__).parent.parent / "shelf.json"))
        self.sessionpath = self.config / "sessions.json"
        self.sessions = load(self.sessionpath) if self.sessionpath.exists() else {}
        self.ready = set()
        self.message = "Ready"
        self.busy = False
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
        require(sum(bool(v.get("enabled")) for v in self.state["modules"].values()) <= MAX_MODULES, "The shelf supports up to 16 enabled toys")
        atomic(self.statepath, self.state)
        self.layout()

    def layout(self):
        data = load(self.layoutpath)
        data["objects"] = [ADAPTERS[k]["overlay"] if k in ADAPTERS else "magicshelf.module." + k for k, v in self.state["modules"].items() if v.get("enabled")]
        require(len(data["objects"]) <= MAX_MODULES, "The shelf supports up to 16 enabled toys")
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

    def unit(self, key):
        return ADAPTERS[key]["shell"] if key in ADAPTERS else "magicshelf-module-" + key + ".service"

    def modulepath(self, key, ver):
        return self.root / "modules" / key / "versions" / ver

    def metadata(self, key, state):
        if key in ADAPTERS:
            return {**ADAPTERS[key], "id": key, "version": state["version"], "permissions": ["vr-overlay"], "license": "Existing local installation", "architecture": machine()}
        return load(self.modulepath(key, state["version"]) / "module.json")

    def write_unit(self, key):
        state = self.state["modules"][key]
        if key in ADAPTERS:
            return
        meta = self.metadata(key, state)
        directory = self.modulepath(key, state["version"])
        data = self.root / "module-data" / key
        data.mkdir(parents=True, exist_ok=True)
        session = secrets.token_hex(24)
        self.sessions[key] = session
        atomic(self.sessionpath, self.sessions)
        self.ready.discard(key)
        env = {"MAGICSHELF_API_VERSION": "1", "MAGICSHELF_MODULE_ID": key, "MAGICSHELF_MODULE_KEY": "magicshelf.module." + key, "MAGICSHELF_SESSION": session, "MAGICSHELF_DATA_DIR": str(data), "MAGICSHELF_RUNTIME_DIR": str(self.runtime), "MAGICSHELF_LAYOUT_DIR": str(self.config), "MAGICSHELF_SHELF_OWNER": "0"}
        lines = ["[Unit]", "Description=MagicShelf module " + key, "BindsTo=steamvr.service", "After=steamvr.service magicshelf.service", "PartOf=steamvr.service", "StartLimitIntervalSec=60", "StartLimitBurst=3", "", "[Service]", "Type=simple", "ExecStart=" + quote(directory / meta["entrypoint"]), "WorkingDirectory=" + str(directory).replace("%", "%%"), "Restart=on-failure", "RestartSec=5", "TimeoutStopSec=10", "NoNewPrivileges=yes", "UMask=0077", "MemoryMax=" + str(meta.get("memory_mb", 256)) + "M", "MemorySwapMax=64M", "Nice=5"]
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
        if key in ADAPTERS:
            self.system.call("start", *ADAPTERS[key]["backends"])
        self.system.call("reset-failed", self.unit(key), check=False)
        self.system.call("start", self.unit(key))
        until = time.monotonic() + 20
        while time.monotonic() < until:
            if key in ADAPTERS:
                result = subprocess.run([str(self.legacy / ADAPTERS[key]["binary"]), "--status"], timeout=3, capture_output=True)
                if result.returncode == 0:
                    subprocess.run([str(self.legacy / ADAPTERS[key]["binary"]), "--dock"], timeout=3, check=True)
                    return
            elif key in self.ready and self.system.active(self.unit(key)):
                return
            time.sleep(.25)
        raise ContractError("Toy did not become ready; its previous version has been restored")

    def hide_adapter(self, key):
        marker = self.legacy / "magicshelf-api-version"
        require(marker.is_file() and marker.read_text().strip() == "2",
                "Update the local device shells before hiding devices; this preserves their live display connection")
        if self.system.active(self.unit(key)):
            subprocess.run([str(self.legacy / ADAPTERS[key]["binary"]), "--hide"], timeout=3, check=True)
        # Keep a running capture connected, but do not auto-start a hidden shell.
        self.system.call("disable", self.unit(key), check=False)

    def toggle(self, key, enabled):
        require(type(enabled) is bool, "enabled must be true or false")
        require(key in self.state["modules"], "Toy is not installed")
        with self.transaction():
            old = self.state["modules"][key]["enabled"]
            require(not enabled or old or sum(bool(i["enabled"]) for i in self.state["modules"].values()) < MAX_MODULES, "The shelf is full")
            self.state["modules"][key]["enabled"] = enabled
            self.save()
            try:
                if enabled:
                    if not self.system.active(self.unit(key)):
                        self.start(key)
                    elif key in ADAPTERS:
                        self.system.call("enable", self.unit(key))
                        subprocess.run([str(self.legacy / ADAPTERS[key]["binary"]), "--dock"], timeout=3, check=True)
                elif key in ADAPTERS:
                    self.hide_adapter(key)
                else:
                    self.system.call("disable", "--now", self.unit(key), check=False)
            except Exception:
                self.state["modules"][key]["enabled"] = old
                self.save()
                if not old:
                    if key in ADAPTERS:
                        self.hide_adapter(key)
                    else:
                        self.system.call("disable", "--now", self.unit(key), check=False)
                raise
            self.message = ("Enabled " if enabled else "Turned off ") + self.metadata(key, self.state["modules"][key])["name"]
        return self.snapshot()

    def open(self, key):
        require(key in ADAPTERS and key in self.state["modules"], "This toy does not support opening from the library")
        self.toggle(key, True)
        subprocess.run([str(self.legacy / ADAPTERS[key]["binary"]), "--show"], timeout=3, check=True)
        self.message = "Opened " + ADAPTERS[key]["name"]
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
                    if item["id"] not in seen and item["id"] not in ADAPTERS and item["architecture"] == machine():
                        items.append({**item, "catalog_url": url})
                        seen.add(item["id"])
            self.state["catalog"] = items
            self.save()
            self.message = "Collection updated"
        return self.snapshot()

    def install(self, key, permissions):
        item = next((i for i in self.state["catalog"] if i["id"] == key), None)
        require(item is not None, "Toy is not in a followed collection")
        require(isinstance(permissions, list) and set(permissions) == set(item["permissions"]), "Review this toy's permissions before installing")
        old = self.state["modules"].get(key)
        require(not old or not old.get("catalog_url") or old["catalog_url"] == item["catalog_url"], "A different collection cannot replace this toy")
        with self.transaction():
            with tempfile.TemporaryDirectory(dir=self.root) as temp:
                archive = Path(temp) / "module.magicshelf"
                download(item["url"], archive, item["size_bytes"])
                require(archive.stat().st_size == item["size_bytes"], "Package size differs from catalog")
                staged = Path(temp) / "unpacked"
                unpack(archive, staged, item["sha256"], item)
                return self.commit_package(key, item["version"], staged, item["catalog_url"])

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
        # Repair interrupted toggles without restarting healthy toys or backends.
        with self.transaction():
            self.layout()
            for key, item in list(self.state["modules"].items()):
                try:
                    if item["enabled"]:
                        if not self.system.active(self.unit(key)):
                            self.start(key)
                    elif key in ADAPTERS:
                        self.hide_adapter(key)
                    else:
                        self.system.call("disable", "--now", self.unit(key), check=False)
                except Exception as e:
                    self.message = "Could not start " + key + ": " + str(e)

    def rollback(self, key):
        require(key in self.state["modules"] and key not in ADAPTERS, "Only packaged toys support version rollback")
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
                self.message = "Restored previous toy version and its saved data"
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
        require(key in self.state["modules"], "Toy is not installed")
        require(key not in ADAPTERS, "Local devices can be turned off; MagicShelf does not delete their existing installations")
        with self.transaction():
            self.system.call("disable", "--now", self.unit(key), check=False)
            self.state["modules"].pop(key)
            self.save()
            (self.units / self.unit(key)).unlink(missing_ok=True)
            self.system.call("daemon-reload")
            shutil.rmtree(self.root / "modules" / key)
            self.message = "Toy removed; its saved data is kept"
        return self.snapshot()

    def home_all(self):
        for key, state in list(self.state["modules"].items()):
            if state["enabled"] and key in ADAPTERS and self.system.active(self.unit(key)):
                subprocess.run([str(self.legacy / ADAPTERS[key]["binary"]), "--dock"], check=True, timeout=5)
        # New modules read their own home-generation counter through the SDK.
        data = {"api_version": 1, "generation": time.time_ns()}
        atomic(self.runtime / "home.json", data)
        self.message = "Returned toys home"
        return self.snapshot()

    def snapshot(self):
        modules = []
        for key, state in list(self.state["modules"].items()):
            try:
                meta = self.metadata(key, state)
                modules.append({**meta, "installed": True, "enabled": state["enabled"], "running": self.system.active(self.unit(key)), "adapter": key in ADAPTERS, "previous_version": state.get("previous_version")})
            except (OSError, ValueError):
                modules.append({"id": key, "name": key, "version": state["version"], "description": "Module files are missing; restore or remove this toy.", "installed": True, "enabled": False, "running": False, "broken": True})
        installed = {i["id"]: i for i in modules}
        for item in self.state["catalog"]:
            if item["id"] not in installed:
                modules.append({**item, "installed": False, "enabled": False})
            elif version(item["version"]) > version(installed[item["id"]]["version"]):
                installed[item["id"]]["update"] = item
        return {"api_version": 1, "version": VERSION, "modules": modules, "catalogs": self.state["catalogs"], "busy": self.busy, "message": self.message}

    def publish(self):
        atomic(self.runtime / "ui-state.json", self.snapshot())
