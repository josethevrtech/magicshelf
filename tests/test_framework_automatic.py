import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from magicshelf.manager import Manager, atomic
from test_framework import FakeSystem


class AutomaticFrameworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        p = Path(self.tmp.name)
        self.system = FakeSystem()
        self.manager = Manager(p/'home', p/'run', self.system)
        self.update = self.manager.framework
        (self.update.root/'1.0.0/magicshelf').mkdir(parents=True)
        atomic(self.update.path, dict(stage='ready', version='1.0.0', sha256='a'*64))

    def tearDown(self):
        self.tmp.cleanup()

    def activity(self, **changes):
        atomic(self.manager.runtime/'dashboard-activity.json',
               dict(pid=123, time=100, visible=False, busy=False, **changes))

    def test_visible_busy_stale_or_wrong_process_cannot_trigger_update(self):
        self.system.running.add('magicshelf-vr.service')
        for change in ({'visible': True}, {'busy': True}, {'time': 90}, {'time': 110}, {'pid': 456}):
            atomic(self.manager.runtime/'dashboard-activity.json',
                   {**dict(pid=123, time=100, visible=False, busy=False), **change})
            self.update.quiet_since = 0
            with patch('magicshelf.framework_updates.time.time', return_value=100), patch.object(self.system, 'call', return_value=types.SimpleNamespace(stdout='123')), patch.object(self.update, 'install') as install:
                self.update.automatic_install()
                install.assert_not_called()
                self.assertIsNone(self.update.quiet_since)
        (self.manager.runtime/'dashboard-activity.json').write_text('broken')
        with patch.object(self.update, 'install') as install:
            self.update.automatic_install()
            install.assert_not_called()

    def test_hidden_app_waits_then_updates_without_reopening(self):
        self.system.running.add('magicshelf-vr.service')
        self.activity()
        with patch('magicshelf.framework_updates.time.time', return_value=100), patch('magicshelf.framework_updates.time.monotonic', side_effect=[100, 129, 131]), patch.object(self.system, 'call', return_value=types.SimpleNamespace(stdout='123')), patch.object(self.update, 'spawn_worker') as spawn:
            self.update.automatic_install()
            self.update.automatic_install()
            spawn.assert_not_called()
            self.update.automatic_install()
            spawn.assert_called_once()
        state = self.update.snapshot()
        self.assertEqual(state['stage'], 'installing')
        self.assertFalse(state['reopen'])
        self.assertTrue(state['automatic_attempted'])

    def test_closed_app_can_update_but_download_and_setup_wait(self):
        with patch.object(self.update, 'install') as install:
            for block in ('busy', 'sync', 'refresh', 'setup', 'download'):
                self.update.quiet_since = 0
                if block == 'busy': self.manager.busy = True
                if block == 'sync': self.manager._sync_lock.acquire()
                if block == 'refresh': self.manager._refresh_lock.acquire()
                if block == 'setup': self.manager.setup.thread = types.SimpleNamespace(is_alive=lambda: True)
                if block == 'download': self.manager._install_thread = types.SimpleNamespace(is_alive=lambda: True)
                self.update.automatic_install()
                self.assertIsNone(self.update.quiet_since)
                self.manager.busy = False
                if block == 'sync': self.manager._sync_lock.release()
                if block == 'refresh': self.manager._refresh_lock.release()
                self.manager.setup.thread = self.manager._install_thread = None
            install.assert_not_called()
            with patch('magicshelf.framework_updates.time.monotonic', side_effect=[100, 131]):
                self.update.automatic_install(); self.update.automatic_install()
            install.assert_called_once_with(automatic=True)

    def test_failed_auto_attempt_survives_restart_without_loop_and_manual_retry_works(self):
        with patch.object(self.update, 'spawn_worker', side_effect=OSError('failed')), self.assertRaises(OSError):
            self.update.install(automatic=True)
        restored = Manager(self.manager.home, self.manager.runtime, self.system).framework
        with patch.object(restored, 'spawn_worker') as spawn:
            restored.automatic_install()
            spawn.assert_not_called()
            restored.install()
            spawn.assert_called_once()
        self.assertTrue(restored.snapshot()['reopen'])

    def test_subscription_work_does_not_start_during_framework_install(self):
        atomic(self.update.path, dict(stage='installing', version='1.0.0'))
        with patch.object(self.manager, 'refresh') as refresh:
            self.manager.sync_subscriptions()
            refresh.assert_not_called()
