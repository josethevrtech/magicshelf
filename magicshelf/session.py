"""Reach the user's services without changing the desktop dialog environment."""
import os
from pathlib import Path


def user_runtime():
    # Steam Frame's nested Plasma has its own runtime and D-Bus session, but
    # MagicShelf and SteamVR run under the real per-user systemd manager.
    runtime = Path('/run/user') / str(os.getuid())
    try:
        if runtime.stat().st_uid == os.getuid() and (runtime/'systemd/private').is_socket():
            return runtime
    except OSError:
        pass
    return Path(os.environ.get('XDG_RUNTIME_DIR', str(runtime)))


def service_environment():
    env = os.environ.copy()
    runtime = user_runtime()
    env['XDG_RUNTIME_DIR'] = str(runtime)
    if (runtime/'bus').is_socket():
        env['DBUS_SESSION_BUS_ADDRESS'] = 'unix:path=' + str(runtime/'bus')
    return env
