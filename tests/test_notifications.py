import unittest
from unittest.mock import patch
import test_update_recovery as recovery
from magicshelf.manager import Manager
from magicshelf.notifications import acknowledge


class UpdateNoticeTests(unittest.TestCase):
    setUp = recovery.UpdateRecoveryTests.setUp
    tearDown = recovery.UpdateRecoveryTests.tearDown
    release = recovery.UpdateRecoveryTests.release
    download = recovery.UpdateRecoveryTests.download
    initial = recovery.UpdateRecoveryTests.initial
    sync = recovery.UpdateRecoveryTests.sync

    def pending(self):
        self.initial(enabled=True)
        self.release('1.1.0')
        self.sync()
        return self.manager.snapshot()['update_notices'][0]

    def test_only_completed_verified_running_updates_make_notices(self):
        self.initial(enabled=True)
        self.release('1.1.0')
        self.assertEqual(self.manager.snapshot()['update_notices'], [])
        self.sync()
        notice=self.manager.snapshot()['update_notices'][0]
        self.assertFalse(notice['announced']);self.assertFalse(notice['dismissed'])
        self.assertEqual(self.manager.state['modules'][self.key]['version'],'1.0.0')
        self.manager.download_path(self.key,self.manager.state['pending_updates'][self.key]).unlink()
        self.assertEqual(self.manager.snapshot()['update_notices'], [])

    def test_announced_marker_survives_restart_without_touching_processes(self):
        notice=self.pending();calls=list(self.system.calls)
        acknowledge(self.manager,self.key,notice['token'],'announced')
        restored=Manager(self.root/'home',self.root/'runtime',self.system)
        self.assertTrue(restored.snapshot()['update_notices'][0]['announced'])
        self.assertEqual(self.system.calls,calls)
        self.assertEqual((self.data/'save').read_text(),'original save')

    def test_later_does_not_stop_redownload_or_remove_pending_update(self):
        notice=self.pending();calls=list(self.system.calls)
        acknowledge(self.manager,self.key,notice['token'],'later')
        self.assertEqual(self.sync().call_count,0)
        self.assertEqual(self.system.calls,calls)
        self.assertIn(self.key,self.manager.state['pending_updates'])
        after=self.manager.snapshot()['update_notices'][0]
        self.assertTrue(after['dismissed']);self.assertTrue(after['announced'])

    def test_newer_version_has_a_fresh_notice(self):
        notice=self.pending();acknowledge(self.manager,self.key,notice['token'],'later')
        self.release('1.2.0');self.sync()
        after=self.manager.snapshot()['update_notices'][0]
        self.assertNotEqual(after['token'],notice['token'])
        self.assertFalse(after['announced']);self.assertFalse(after['dismissed'])
        with self.assertRaisesRegex(ValueError,'no longer current'):
            acknowledge(self.manager,self.key,notice['token'],'later')

    def test_off_installs_after_later_and_removes_notice(self):
        notice=self.pending();acknowledge(self.manager,self.key,notice['token'],'later')
        with patch('magicshelf.manager.download') as download:self.manager.toggle(self.key,False)
        download.assert_not_called()
        self.assertEqual(self.manager.snapshot()['update_notices'],[])
        self.assertEqual(self.manager.state['modules'][self.key]['version'],'1.1.0')
        self.assertEqual((self.data/'save').read_text(),'original save')

    def test_withdrawn_update_does_not_leave_a_notification(self):
        self.pending();self.release('1.0.0');self.sync()
        self.assertEqual(self.manager.snapshot()['update_notices'],[])

    def test_unknown_actions_cannot_acknowledge_or_stop_a_creation(self):
        notice=self.pending();calls=list(self.system.calls)
        with self.assertRaises(ValueError):acknowledge(self.manager,self.key,notice['token'],'install')
        self.assertEqual(self.system.calls,calls)
