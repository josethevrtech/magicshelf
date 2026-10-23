import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from magicshelf.collections import OFFICIAL, DIRECTORY, catalogs
from magicshelf.manager import Manager
from magicshelf.server import dispatch
from test_framework import FakeSystem, meta
from tools.sync_catalog import sync


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manager = Manager(self.root/'home', self.root/'run', FakeSystem())
        self.manager.state['catalogs'] = [OFFICIAL]
        self.source = 'https://github.com/josethevrtech/new-creation/releases/latest/download/catalog.json'
        self.item = {**meta(), 'url': 'https://github.com/josethevrtech/new-creation/releases/download/v1.0.0/creation.magicshelf', 'sha256': 'a'*64, 'size_bytes': 100}
        self.directory = {'schema_version': 1, 'catalogs': [self.source]}
        self.fail = set()

    def tearDown(self):
        self.temp.cleanup()

    def fetch(self, url, path, limit, progress=None):
        if url in self.fail:
            raise TimeoutError('offline')
        data = self.directory if url == DIRECTORY else {'schema_version': 1, 'name': 'Test', 'modules': [self.item] if url == self.source else []}
        path.write_text(json.dumps(data))

    def refresh(self, manager=None):
        manager = manager or self.manager
        with patch('magicshelf.manager.download', side_effect=self.fetch), patch.object(manager, 'cache_previews'):
            manager.refresh()

    def test_new_publication_reaches_existing_install_without_subscribing(self):
        self.manager.save()
        self.refresh()
        state = self.manager.snapshot()
        creation = next(m for m in state['modules'] if m['id'] == self.item['id'])
        self.assertFalse(creation['installed'])
        self.assertFalse(creation['subscribed'])
        self.assertEqual(creation['catalog_url'], self.source)
        self.assertEqual(self.manager.state['subscriptions'], {})
        restored = Manager(self.manager.home, self.manager.runtime, FakeSystem())
        self.assertIn(self.source, restored.state['catalogs'])

    def test_uninstall_retains_discover_listing_across_restart_and_offline_refresh(self):
        self.refresh()
        staged = self.root/'stage'; staged.mkdir()
        (staged/'module.json').write_text(json.dumps(meta()))
        self.manager.commit_package(self.item['id'], '1.0.0', staged, self.source)
        self.manager.remove(self.item['id'])
        restored = Manager(self.manager.home, self.manager.runtime, FakeSystem())
        self.fail = set(restored.state['catalogs']) | {DIRECTORY}
        self.refresh(restored)
        creation = next(m for m in restored.snapshot()['modules'] if m['id'] == self.item['id'])
        self.assertFalse(creation['installed'])
        self.assertTrue(creation['subscription_available'])
        self.assertIn(self.source, restored.state['catalogs'])

    def test_bad_directory_does_not_hide_known_creations_or_add_untrusted_urls(self):
        self.refresh()
        self.directory = {'schema_version': 1, 'catalogs': ['https://example.org/catalog.json']}
        self.refresh()
        self.assertIn(DIRECTORY, self.manager.catalog_errors)
        self.assertNotIn('https://example.org/catalog.json', self.manager.state['catalogs'])
        self.assertTrue(any(m['id'] == self.item['id'] for m in self.manager.snapshot()['modules']))

    def test_independent_latest_catalog_wins_over_compatibility_mirror(self):
        old = {**self.item, 'version': '0.9.0'}
        def fetch(url, path, limit, progress=None):
            if url == OFFICIAL:
                path.write_text(json.dumps({'schema_version': 1, 'name': 'Mirror', 'modules': [old]}))
            else:
                self.fetch(url, path, limit, progress)
        with patch('magicshelf.manager.download', side_effect=fetch), patch.object(self.manager, 'cache_previews'):
            self.manager.refresh()
        self.assertEqual(self.manager.state['catalog'][0]['version'], '1.0.0')
        self.assertEqual(self.manager.state['catalog'][0]['catalog_url'], self.source)

    def test_discover_reuses_recent_check_and_requests_a_stale_one(self):
        self.manager.state['last_update_check'] = time.time()
        with patch.object(self.manager, 'request_update_check', return_value={}) as check:
            dispatch(self.manager, {'api_version': 1, 'method': 'catalog.discover'})
            check.assert_not_called()
            self.manager.state['last_update_check'] = 0
            dispatch(self.manager, {'api_version': 1, 'method': 'catalog.discover'})
            check.assert_called_once()

    def test_directory_is_bounded_and_deduplicated(self):
        self.assertEqual(catalogs({'schema_version': 1, 'catalogs': [self.source]*2}), [self.source])
        for data in ([], {'schema_version': 1, 'catalogs': [self.source]*65}, {'schema_version': 1, 'catalogs': ['https://github.com/other/new/releases/latest/download/catalog.json']}):
            with self.assertRaises(ValueError):
                catalogs(data)

    def test_compatibility_mirror_keeps_offline_entries_and_follows_latest_metadata(self):
        other = self.source.replace('new-creation', 'other-creation')
        old = {**self.item, 'collection_url': other, 'id': 'org.test.other'}
        (self.root/'collections.json').write_text(json.dumps({'schema_version': 1, 'catalogs': [self.source, other]}))
        (self.root/'catalog.json').write_text(json.dumps({'schema_version': 1, 'name': 'Old', 'modules': [old]}))
        self.fail.add(other)
        with patch('tools.sync_catalog.download', side_effect=self.fetch):
            result = sync(self.root)
        self.assertEqual({m['id'] for m in result['modules']}, {self.item['id'], old['id']})
        self.assertEqual(result['modules'][0]['collection_url'], self.source)
        before = (self.root/'catalog.json').read_bytes()
        self.fail.add(self.source)
        with patch('tools.sync_catalog.download', side_effect=self.fetch), self.assertRaises(RuntimeError):
            sync(self.root)
        self.assertEqual((self.root/'catalog.json').read_bytes(), before)
