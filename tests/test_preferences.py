import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from magicshelf.contracts import ContractError, load
from magicshelf.manager import Manager
from magicshelf.server import dispatch
from magicshelf import preferences
from test_framework import FakeSystem


class PreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.system = FakeSystem()
        self.manager = Manager(self.root / 'home', self.root / 'runtime', self.system)

    def tearDown(self):
        self.temp.cleanup()

    def test_settings_persist_without_restarting_creations(self):
        old = load(self.manager.layoutpath)
        result = dispatch(self.manager, {'api_version': 1, 'method': 'settings.update', 'params': {'changes': {'slot_spacing_m': .16, 'dashboard_width_m': 2., 'start_view': 'library'}}})
        self.assertEqual(result['preferences']['values']['slot_spacing_m'], .16)
        restored = Manager(self.root / 'home', self.root / 'runtime', self.system)
        values = restored.snapshot()['preferences']['values']
        self.assertEqual(values['dashboard_width_m'], 2.)
        self.assertEqual(values['start_view'], 'library')
        layout = load(restored.layoutpath)
        self.assertEqual(layout['objects'], old['objects'])
        self.assertEqual(layout['anchor_overlay'], old['anchor_overlay'])
        self.assertFalse(self.system.calls)
        self.assertTrue((restored.runtime / 'home.json').exists())

    def test_rejects_invalid_settings_atomically(self):
        before = self.manager.layoutpath.read_bytes()
        for changes in [None, [], {}, {'objects': []}, {'opacity': True}, {'opacity': float('nan')}, {'depth_m': float('inf')}, {'object_height_m': .25}, {'launcher_only': 1}, {'start_view': 'billing'}, {'opacity': .5, 'depth_m': 100}]:
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                self.manager.update_settings(changes)
            self.assertEqual(self.manager.layoutpath.read_bytes(), before)

    def test_layout_reset_returns_creations_even_when_values_already_default(self):
        with patch.object(self.manager, 'home_all', wraps=self.manager.home_all) as home:
            self.manager.reset_settings('placement')
            self.manager.reset_settings('placement')
            self.assertEqual(home.call_count, 2)
        self.manager.update_settings({'start_view': 'library', 'opacity': .5})
        self.manager.reset_settings('shelf')
        values = self.manager.snapshot()['preferences']['values']
        self.assertEqual(values['opacity'], preferences.defaults()['opacity'])
        self.assertEqual(values['start_view'], 'library')

    def test_app_and_opacity_changes_do_not_reposition_creations(self):
        with patch.object(self.manager, 'home_all') as home:
            self.manager.update_settings({'dashboard_width_m': 2.1, 'opacity': .6, 'launcher_only': False})
            self.manager.reset_settings('app')
            home.assert_not_called()

    def test_app_links_are_limited_to_published_credits(self):
        for index in [-1, 3, True, 'https://elsewhere.example']:
            with self.assertRaises(ContractError):
                self.manager.app_link(index)
        with patch('magicshelf.manager.subprocess.run') as run:
            self.manager.app_link(0)
            self.assertEqual(run.call_args.args[0], ['xdg-open', 'https://github.com/josethevrtech'])
