import os
from pathlib import Path
import types
import unittest
from unittest.mock import patch

from magicshelf import client, session


class SessionTests(unittest.TestCase):
    def test_nested_desktop_reaches_main_user_services_without_changing_dialogs(self):
        desktop = {'XDG_RUNTIME_DIR': '/run/user/1000/nested_plasma',
                   'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/tmp/desktop-bus',
                   'WAYLAND_DISPLAY': 'wayland-0', 'DISPLAY': ':2'}
        sockets = {'/run/user/1000/systemd/private', '/run/user/1000/bus'}
        with patch.dict(os.environ, desktop, clear=True), patch.object(os, 'getuid', return_value=1000), \
                patch.object(Path, 'stat', return_value=types.SimpleNamespace(st_uid=1000)), \
                patch.object(Path, 'is_socket', lambda p: str(p) in sockets):
            env = session.service_environment()
            self.assertEqual(env['XDG_RUNTIME_DIR'], '/run/user/1000')
            self.assertEqual(env['DBUS_SESSION_BUS_ADDRESS'], 'unix:path=/run/user/1000/bus')
            self.assertEqual(env['WAYLAND_DISPLAY'], 'wayland-0')
            self.assertEqual(env['DISPLAY'], ':2')
            self.assertEqual(client.runtime_dir(), Path('/run/user/1000/magicshelf'))
            self.assertEqual(dict(os.environ), desktop)

    def test_missing_user_manager_preserves_explicit_session_runtime(self):
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': '/tmp/isolated-session', 'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/tmp/test-bus'}), \
                patch.object(Path, 'stat', side_effect=FileNotFoundError(2, 'No such file or directory')):
            self.assertEqual(session.service_environment()['XDG_RUNTIME_DIR'], '/tmp/isolated-session')
            self.assertEqual(session.service_environment()['DBUS_SESSION_BUS_ADDRESS'], 'unix:path=/tmp/test-bus')

    def test_runtime_owned_by_another_user_is_not_selected(self):
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': '/tmp/own-session'}), \
                patch.object(Path, 'stat', return_value=types.SimpleNamespace(st_uid=-1)):
            self.assertEqual(session.user_runtime(), Path('/tmp/own-session'))


if __name__ == '__main__': unittest.main()
