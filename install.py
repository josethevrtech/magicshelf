#!/usr/bin/env python3
"""Per-user installation; no root commands, OS changes, or game data copying."""
import contextlib
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
import importlib.util

# Automatic updates import this installer inside the previous framework. Load
# the verified new helper directly, even when the old package is already loaded.
_session_spec = importlib.util.spec_from_file_location('installer_session', Path(__file__).resolve().parent/'magicshelf/session.py')
_session = importlib.util.module_from_spec(_session_spec)
_session_spec.loader.exec_module(_session)
service_environment, user_runtime = _session.service_environment, _session.user_runtime

def system(*args, check=True):
    result = subprocess.run(["systemctl", "--user", *args], env=service_environment(), timeout=40, capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError('Could not start MagicShelf services: ' + (result.stderr.strip() or result.stdout.strip() or 'systemctl failed'))
    return result

def install(source=None, *, automatic=False):
    with contextlib.ExitStack() as resources:
        return _install(source, resources, automatic)

def _install(source, resources, automatic=False):
    if os.geteuid() == 0:
        raise RuntimeError('Open Install MagicShelf from your own desktop. No administrator password is needed.')
    source = Path(source).resolve() if source else Path(__file__).resolve().parent
    metadata = json.loads((source / "release.json").read_text())
    import hashlib
    for name, digest in metadata["files"].items():
        path = source / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Release file verification failed: " + name)
    import platform
    if platform.system() != "Linux" or platform.machine() != metadata["architecture"]:
        raise RuntimeError("This MagicShelf download is for Linux " + metadata["architecture"])
    if not (Path("/opt/steamvr/bin") / ("linuxarm64" if metadata["architecture"] == "aarch64" else "linux64") / "libopenvr_api.so").is_file():
        raise RuntimeError("Install and start SteamVR normally before installing MagicShelf.")
    # Check the user service connection before staging or changing integration.
    system('show', '--property=Version', '--value')
    home = Path.home()
    root = home / ".local/share/magicshelf"
    root.mkdir(parents=True, exist_ok=True)
    lock = resources.enter_context((root / "install.lock").open("a"))
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    marker = root / 'uninstalled'
    was_uninstalled = marker.exists()
    if automatic and marker.exists():
        raise RuntimeError('MagicShelf was uninstalled. Automatic installation was cancelled.')
    releases = root / "releases"
    releases.mkdir(exist_ok=True)
    target = releases / metadata["version"]
    current = root / "current"
    previous = current.resolve() if current.is_symlink() and not was_uninstalled else None
    if target.exists():
        # Idempotent reinstall only; versioned releases must be immutable.
        if (target / "release.json").read_bytes() != (source / "release.json").read_bytes():
            raise RuntimeError("That version is already installed with different contents; publish a new version.")
        for name, digest in metadata["files"].items():
            if hashlib.sha256((target / name).read_bytes()).hexdigest() != digest:
                raise RuntimeError("An installed release file changed; restore or install a newer release.")
    else:
        staged = releases / (metadata["version"] + ".next")
        if staged.exists():
            shutil.rmtree(staged)
        shutil.copytree(source, staged)
        staged.rename(target)
    units = home / ".config/systemd/user"
    units.mkdir(parents=True, exist_ok=True)
    backup = root / "install-backups" / str(time.time_ns())
    backup.mkdir(parents=True)
    for name in ("magicshelf.service", "magicshelf-vr.service"):
        if (units / name).exists():
            shutil.copy2(units / name, backup / name)
    try:
        marker.unlink(missing_ok=True)
        nextlink = root / "current.next"
        nextlink.unlink(missing_ok=True)
        nextlink.symlink_to(target)
        os.replace(nextlink, current)
        (units / "magicshelf.service").write_text("""[Unit]
Description=MagicShelf module manager
After=graphical-session.target

[Service]
ExecStart=%h/.local/share/magicshelf/current/bin/magicshelf serve
Restart=on-failure
RestartSec=5
MemoryMax=192M
NoNewPrivileges=yes
UMask=0077

[Install]
WantedBy=default.target
""")
        (units / "magicshelf-vr.service").write_text("""[Unit]
Description=MagicShelf shelf and module library
BindsTo=steamvr.service
After=steamvr.service magicshelf.service
Wants=magicshelf.service
PartOf=steamvr.service

[Service]
ExecStart=%h/.local/share/magicshelf/current/bin/magicshelf-vr
Environment=MAGICSHELF_LAYOUT_DIR=%h/.config/magicshelf
Environment=MAGICSHELF_RUNTIME_DIR=%t/magicshelf
Restart=on-failure
RestartSec=5
MemoryMax=512M
MemorySwapMax=64M
NoNewPrivileges=yes
UMask=0077

[Install]
WantedBy=steamvr.service
""")
        system("daemon-reload")
        config = home / ".config/magicshelf"
        config.mkdir(parents=True, exist_ok=True)
        manifest = {"source": "user", "applications": [{"app_key": "com.josethevrtech.magicshelf", "launch_type": "binary", "binary_path_linux": str(current / "bin/magicshelf-vr-launch"), "binary_path_linux_arm": str(current / "bin/magicshelf-vr-launch"), "is_dashboard_overlay": True, "strings": {"en_us": {"name": "MagicShelf", "description": "A home for my VR creations."}}}]}
        (config / "magicshelf.vrmanifest").write_text(json.dumps(manifest, indent=2) + "\n")
        system("enable", "magicshelf.service", "magicshelf-vr.service")
        system("restart", "magicshelf.service")
        runtime = user_runtime() / "magicshelf"
        sys.path.insert(0, str(current))
        from magicshelf.client import request
        for attempt in range(50):
            try:
                ready = request("snapshot", timeout=3)
                if ready.get("version") != metadata["version"]:
                    raise RuntimeError("MagicShelf is still starting")
                break
            except (OSError, RuntimeError):
                if attempt == 49:
                    raise RuntimeError("The MagicShelf manager did not become ready")
                time.sleep(.1)
        # Adoption is opt-in for known migrated local devices; no game is downloaded.
        legacy = home / "Applications/DigitalPartner/vr"
        if (legacy / "magicshelf-api-version").exists() and (legacy / "magicshelf-api-version").read_text().strip() == "1":
            request("modules.adopt")
        # The first-party example package is included in the verified framework bundle.
        subprocess.run([str(current / "bin/magicshelf-bootstrap")], check=True, timeout=30)
        if system("is-active", "--quiet", "steamvr.service", check=False).returncode == 0:
            system("restart", "magicshelf-vr.service")
            for attempt in range(100):
                try:
                    pid = int(system('show', 'magicshelf-vr.service', '-p', 'MainPID', '--value').stdout.strip())
                    rendered = json.loads((runtime/'dashboard-render.json').read_text())
                    if pid > 0 and rendered.get('pid') == pid and rendered.get('frames', 0) > 0:
                        break
                except (OSError, ValueError):
                    pass
                if attempt == 99:
                    raise RuntimeError('MagicShelf could not open. Your previous version will be restored.')
                time.sleep(.1)
        app = home / ".local/share/applications/com.josethevrtech.magicshelf.desktop"
        app.parent.mkdir(parents=True, exist_ok=True)
        icon = home / '.local/share/icons/hicolor/512x512/apps/com.josethevrtech.magicshelf.png'
        icon.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(current/'icon.png', icon)
        # No % or shell expansion in desktop Exec; quote the complete executable path.
        executable = str(current / "bin/magicshelf").replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "\\$").replace("`", "\\`")
        app.write_text('[Desktop Entry]\nType=Application\nName=MagicShelf\nComment=A home for my VR creations.\nExec="' + executable + '" open\nIcon=com.josethevrtech.magicshelf\nTerminal=false\nCategories=Game;\n')
        uninstall = home / '.local/share/applications/com.josethevrtech.magicshelf.uninstall.desktop'
        uninstaller = str(current/'uninstall.py').replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '\\$').replace('`', '\\`')
        uninstall.write_text('[Desktop Entry]\nType=Application\nName=Uninstall MagicShelf\nComment=Remove MagicShelf and keep saved data\nExec=python3 "'+uninstaller+'" --gui\nIcon=com.josethevrtech.magicshelf\nTerminal=false\nCategories=Game;\n')
        desktop = home / "Desktop"
        try:
            result = subprocess.run(['xdg-user-dir', 'DESKTOP'], capture_output=True, text=True, timeout=5)
            configured = Path(getattr(result, 'stdout', '').strip())
            if result.returncode == 0 and configured.is_absolute() and configured.is_relative_to(home):
                desktop = configured
        except (OSError, subprocess.SubprocessError):
            pass
        if desktop.is_dir():
            shortcut = desktop / "MagicShelf.desktop"
            shutil.copy2(app, shortcut)
            shortcut.chmod(0o755)
            shortcut = desktop / 'Uninstall MagicShelf.desktop'
            shutil.copy2(uninstall, shortcut)
            shortcut.chmod(0o755)
        print("MagicShelf installed. Open MagicShelf on your desktop or in SteamVR's dashboard.")
    except Exception:
        if was_uninstalled:
            marker.touch()
        if previous:
            nextlink = root / "current.next"
            nextlink.unlink(missing_ok=True)
            nextlink.symlink_to(previous)
            os.replace(nextlink, current)
        else:
            system("disable", "--now", "magicshelf-vr.service", "magicshelf.service", check=False)
            current.unlink(missing_ok=True)
        for name in ("magicshelf.service", "magicshelf-vr.service"):
            if (backup / name).exists():
                shutil.copy2(backup / name, units / name)
            else:
                (units / name).unlink(missing_ok=True)
        system("daemon-reload", check=False)
        if previous:
            system("restart", "magicshelf.service", "magicshelf-vr.service", check=False)
        raise

if __name__ == "__main__":
    try:
        install()
    except Exception as e:
        print("MagicShelf installation failed:", e, file=sys.stderr)
        sys.exit(1)
