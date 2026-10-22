import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from magicshelf.manager import Manager
from test_framework import FakeSystem, meta, package


class UpdateRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.system = FakeSystem()
        self.manager = Manager(self.root/'home', self.root/'runtime', self.system)
        self.key = 'org.test.toy'
        self.source = 'https://raw.githubusercontent.com/test/one/main/catalog.json'
        self.archives = {}

    def tearDown(self):
        self.temp.cleanup()

    def release(self, ver, permissions=None):
        item = meta(ver)
        if permissions:
            item['permissions'] = permissions
        archive = self.root/(ver+'.zip')
        digest = package(archive, item)
        item.update(url='https://github.com/test/one/releases/download/v'+ver+'/creation.magicshelf', sha256=digest,
                    size_bytes=archive.stat().st_size, catalog_url=self.source)
        self.archives[item['url']] = archive
        self.manager.state['catalog'] = [item]
        return item

    def download(self, url, path, limit, progress=None):
        if progress:
            progress(0)
        shutil.copy2(self.archives[url], path)
        if progress:
            progress(path.stat().st_size)

    def initial(self, enabled=False):
        self.release('1.0.0')
        with patch('magicshelf.manager.download', side_effect=self.download):
            self.manager.subscribe(self.key, True, ['vr-overlay'])
        self.manager.state['modules'][self.key]['enabled'] = enabled
        if enabled:
            self.system.running.add(self.manager.unit(self.key))
        self.data = self.manager.root/'module-data'/self.key
        self.data.mkdir(parents=True, exist_ok=True)
        (self.data/'save').write_text('original save')
        self.manager.save()

    def sync(self, **kwargs):
        with patch('magicshelf.manager.download', side_effect=self.download) as download:
            self.manager.sync_subscriptions(refresh=False, **kwargs)
        return download

    def test_running_update_downloads_once_and_installs_after_off_without_network(self):
        self.initial(enabled=True)
        item = self.release('1.1.0')
        before = list(self.system.calls)
        self.assertEqual(self.sync().call_count, 1)
        self.assertEqual(self.manager.state['modules'][self.key]['version'], '1.0.0')
        self.assertEqual(self.system.calls, before)
        self.assertEqual(self.manager.snapshot()['modules'][0]['update_status'], 'ready')
        self.assertTrue(self.manager.download_path(self.key, item).exists())
        self.assertEqual(self.sync().call_count, 0)
        with patch('magicshelf.manager.download') as download:
            self.manager.toggle(self.key, False)
        download.assert_not_called()
        self.assertEqual(self.manager.state['modules'][self.key]['version'], '1.1.0')
        self.assertFalse(self.manager.state['modules'][self.key]['enabled'])
        self.assertEqual((self.data/'save').read_text(), 'original save')
        self.assertNotIn(self.key, self.manager.state['pending_updates'])

    def test_pending_update_survives_restart_without_restarting_active_creation(self):
        self.initial(enabled=True)
        self.release('1.1.0')
        self.sync()
        restored = Manager(self.root/'home', self.root/'runtime', self.system)
        with patch.object(restored, 'start') as start:
            restored.reconcile()
        start.assert_not_called()
        with patch('magicshelf.manager.download') as download:
            restored.toggle(self.key, False)
        download.assert_not_called()
        self.assertEqual(restored.state['modules'][self.key]['version'], '1.1.0')

    def test_unsubscribe_cancels_pending_install(self):
        self.initial(enabled=True)
        self.release('1.1.0')
        self.sync()
        self.manager.subscribe(self.key, False)
        self.manager.toggle(self.key, False)
        self.assertEqual(self.manager.state['modules'][self.key]['version'], '1.0.0')
        self.assertNotIn(self.key, self.manager.state['pending_updates'])

    def test_withdrawn_update_is_not_installed_when_turned_off(self):
        self.initial(enabled=True)
        current = dict(self.manager.state['catalog'][0])
        self.release('1.1.0')
        self.sync()
        self.manager.state['catalog'] = [current]
        self.sync()
        self.manager.toggle(self.key, False)
        self.assertEqual(self.manager.state['modules'][self.key]['version'], '1.0.0')
        self.assertEqual(self.manager.snapshot()['modules'][0]['update_status'], 'current')
        self.assertFalse(list((self.manager.root/'downloads'/self.key).glob('*.magicshelf')))

    def test_failed_stop_does_not_claim_off_or_remove_installed_files(self):
        self.initial(enabled=True)
        with patch.object(self.manager.system, 'call', side_effect=TimeoutError('still stopping')):
            with self.assertRaises(TimeoutError):
                self.manager.toggle(self.key, False)
            self.assertTrue(self.manager.state['modules'][self.key]['enabled'])
            with self.assertRaises(TimeoutError):
                self.manager.remove(self.key)
        self.assertTrue(self.manager.modulepath(self.key, '1.0.0').exists())
        self.assertIn(self.key, self.manager.state['subscriptions'])
        self.assertFalse(self.manager.busy)

    def test_bad_cached_update_keeps_off_and_can_retry(self):
        self.initial(enabled=True)
        item = self.release('1.1.0')
        self.sync()
        self.manager.download_path(self.key, item).write_bytes(b'broken')
        self.manager.toggle(self.key, False)
        self.assertFalse(self.manager.state['modules'][self.key]['enabled'])
        self.assertEqual(self.manager.state['modules'][self.key]['version'], '1.0.0')
        self.assertEqual(self.manager.snapshot()['modules'][0]['update_status'], 'failed')
        self.assertEqual(self.sync(manual=True).call_count, 1)
        self.assertEqual(self.manager.state['modules'][self.key]['version'], '1.1.0')

    def test_failure_backoff_does_not_block_explicit_retry(self):
        self.initial()
        self.release('1.1.0')
        with patch('magicshelf.manager.download', side_effect=TimeoutError('network')):
            self.manager.sync_subscriptions(refresh=False)
        self.assertEqual(self.sync().call_count, 0)
        self.assertEqual(self.sync(manual=True).call_count, 1)

    def test_permissions_are_reviewed_before_download_or_queue(self):
        self.initial(enabled=True)
        self.release('1.1.0', ['vr-overlay', 'network'])
        self.assertEqual(self.sync().call_count, 0)
        self.assertEqual(self.manager.snapshot()['modules'][0]['update_status'], 'review')
        self.assertFalse(self.manager.state['pending_updates'])

    def test_rollback_stays_restored_and_explicit_update_can_reuse_release(self):
        self.initial()
        self.release('1.1.0')
        self.sync()
        (self.data/'save').write_text('new save')
        self.manager.rollback(self.key)
        self.assertEqual((self.data/'save').read_text(), 'original save')
        self.assertEqual(self.sync(manual=True).call_count, 0)
        self.assertEqual(self.manager.snapshot()['modules'][0]['update_status'], 'held')
        with patch('magicshelf.manager.download', side_effect=self.download):
            self.manager.subscribe(self.key, True, ['vr-overlay'])
        self.assertEqual(self.manager.state['modules'][self.key]['version'], '1.1.0')
        self.assertFalse(self.manager.state['held_updates'])

    def test_a_newer_release_is_not_held_after_rollback(self):
        self.initial()
        self.release('1.1.0'); self.sync(); self.manager.rollback(self.key)
        self.release('1.2.0'); self.sync()
        self.assertEqual(self.manager.state['modules'][self.key]['version'], '1.2.0')

    def test_interrupted_update_restores_previous_code_and_data_on_restart(self):
        self.initial(enabled=True)
        self.release('1.1.0')
        def interrupted(key):
            (self.data/'save').write_text('incomplete migration')
            raise SystemExit('simulated process exit')
        with patch.object(self.manager, 'start', side_effect=interrupted), patch('magicshelf.manager.download', side_effect=self.download), self.assertRaises(SystemExit):
            self.manager.subscribe(self.key, True, ['vr-overlay'])
        self.assertEqual(self.manager.state['modules'][self.key]['version'], '1.1.0')
        restored = Manager(self.root/'home', self.root/'runtime', self.system)
        restored.reconcile()
        self.assertEqual(restored.state['modules'][self.key]['version'], '1.0.0')
        self.assertTrue(restored.state['modules'][self.key]['enabled'])
        self.assertEqual((self.data/'save').read_text(), 'original save')
        self.assertFalse(restored.modulepath(self.key, '1.1.0').exists())
        self.assertFalse((restored.config/'pending-install.json').exists())

    def test_interrupted_backup_does_not_restore_an_incomplete_checkpoint(self):
        self.initial(enabled=True)
        self.release('1.1.0')
        def interrupted(source, target, **kwargs):
            target.mkdir(parents=True)
            (target/'save').write_text('partial backup')
            raise SystemExit('simulated process exit')
        with patch('magicshelf.manager.shutil.copytree', side_effect=interrupted), patch('magicshelf.manager.download', side_effect=self.download), self.assertRaises(SystemExit):
            self.manager.subscribe(self.key, True, ['vr-overlay'])
        restored = Manager(self.root/'home', self.root/'runtime', self.system)
        restored.reconcile()
        self.assertEqual((self.data/'save').read_text(), 'original save')
        self.assertEqual(restored.state['modules'][self.key]['version'], '1.0.0')

    def test_unreachable_catalog_keeps_cached_listing_and_healthy_updates_continue(self):
        self.initial()
        newer = self.release('1.1.0')
        missing = 'https://raw.githubusercontent.com/test/offline/main/catalog.json'
        cached = {**meta(), 'id': 'org.test.other', 'catalog_url': missing, 'url': newer['url'], 'sha256': newer['sha256'], 'size_bytes': newer['size_bytes']}
        self.manager.state['catalogs'] = [missing, self.source]
        self.manager.state['catalog'].append(cached)
        def fetch(url, path, limit, progress=None):
            if url == missing:
                raise TimeoutError('offline')
            if url == self.source:
                path.write_text(json.dumps({'schema_version': 1, 'name': 'Test', 'modules': [newer]}))
            else:
                self.download(url, path, limit, progress)
        with patch('magicshelf.manager.download', side_effect=fetch), patch.object(self.manager, 'cache_previews'):
            self.manager.sync_subscriptions()
        self.assertEqual(self.manager.state['modules'][self.key]['version'], '1.1.0')
        self.assertTrue(any(m['id'] == 'org.test.other' for m in self.manager.snapshot()['modules']))
        self.assertIn('could not be checked', self.manager.update_message)

    def test_catalog_network_wait_does_not_lock_normal_actions(self):
        self.initial()
        self.manager.state['catalogs'] = [self.source]
        waiting, release = threading.Event(), threading.Event()
        def fetch(*args, **kwargs):
            waiting.set()
            release.wait(3)
            raise TimeoutError('offline')
        with patch('magicshelf.manager.download', side_effect=fetch), patch.object(self.manager, 'cache_previews'):
            worker = threading.Thread(target=self.manager.refresh)
            worker.start()
            try:
                self.assertTrue(waiting.wait(2))
                self.assertFalse(self.manager.busy)
                self.manager.update_settings({'opacity': .6})
            finally:
                release.set(); worker.join(5)
            self.assertFalse(worker.is_alive())

    def test_manual_check_returns_immediately_and_coalesces_repeat_clicks(self):
        entered, finish = threading.Event(), threading.Event()
        def wait_check(**kwargs):
            entered.set()
            finish.wait(3)
        with patch.object(self.manager, 'sync_subscriptions', side_effect=wait_check) as sync:
            try:
                self.manager.request_update_check()
                self.assertTrue(entered.wait(2))
                result = self.manager.request_update_check()
                self.assertFalse(result['busy'])
                self.assertTrue(result['checking_updates'])
                sync.assert_called_once_with(manual=True)
            finally:
                finish.set(); self.manager._check_thread.join(5)

    def test_first_start_of_bad_offline_update_restores_working_version(self):
        self.initial()
        self.release('1.1.0'); self.sync()
        def start(key):
            if self.manager.state['modules'][key]['version'] == '1.1.0':
                (self.data/'save').write_text('bad migration')
                raise RuntimeError('broken creation')
            self.system.running.add(self.manager.unit(key))
        with patch.object(self.manager, 'start', side_effect=start):
            result = self.manager.toggle(self.key, True)
        self.assertEqual(self.manager.state['modules'][self.key]['version'], '1.0.0')
        self.assertTrue(self.manager.state['modules'][self.key]['enabled'])
        self.assertFalse(result['busy'])
        self.assertEqual((self.data/'save').read_text(), 'original save')
        self.assertEqual(self.manager.state['held_updates'][self.key], '1.1.0')

    def test_interrupted_restore_recovers_the_version_and_saves_before_restore(self):
        self.initial()
        self.release('1.1.0'); self.sync()
        (self.data/'save').write_text('latest save')
        self.manager.state['modules'][self.key]['enabled'] = True
        self.manager.save()
        with patch.object(self.manager, 'start', side_effect=SystemExit('interrupted restore')), self.assertRaises(SystemExit):
            self.manager.rollback(self.key)
        restored = Manager(self.root/'home', self.root/'runtime', self.system)
        restored.reconcile()
        self.assertEqual(restored.state['modules'][self.key]['version'], '1.1.0')
        self.assertEqual((self.data/'save').read_text(), 'latest save')
