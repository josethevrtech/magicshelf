import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from magicshelf import setup
from magicshelf.manager import Manager, atomic
from magicshelf.server import dispatch
from test_framework import FakeSystem, meta


class AutomaticSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manager = Manager(self.root/'home', self.root/'run', FakeSystem())
        self.meta = {**meta(), 'api_version': 2, 'steam_requirements': [
            {'appid': 123, 'title': 'Support', 'files': ['Support/run']},
            {'appid': 456, 'title': 'More support', 'files': ['More/run']} ]}
        self.key = self.meta['id']
        self.staged = self.root/'staged'
        atomic(self.staged/'module.json', self.meta)

    def tearDown(self):
        thread = self.manager.setup.thread
        if thread: thread.join(2)
        self.temp.cleanup()

    def install(self):
        self.manager.commit_package(self.key, '1.0.0', self.staged)

    def installed(self, appid):
        r = next(s for s in self.meta['steam_requirements'] if s['appid'] == appid)
        steam = self.manager.home/'.local/share/Steam/steamapps'
        file = steam/'common'/r['files'][0]
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()
        (steam/f'appmanifest_{appid}.acf').write_text('"StateFlags" "4"')

    def test_approved_install_queues_all_support_without_blocking_or_duplicates(self):
        self.install()
        self.assertEqual(self.manager.setup.snapshot(self.meta)['stage'], 'queued')
        with patch('magicshelf.setup.request_download', side_effect=lambda home, appid: self.installed(appid)) as download:
            self.manager.setup.tick()
            self.manager.setup.thread.join(2)
            self.assertEqual([c.args[1] for c in download.call_args_list], [123,456])
            self.assertTrue(self.manager.setup.snapshot(self.meta)['ready'])
            self.manager.setup.tick()
            self.assertEqual(download.call_count, 2)
        self.assertFalse(self.manager.state['modules'][self.key]['enabled'])

    def test_existing_support_is_reused(self):
        self.installed(123)
        self.install()
        with patch('magicshelf.setup.request_download', side_effect=lambda home, appid: self.installed(appid)) as download:
            self.manager.setup.run(self.key, '1.0.0')
            self.assertEqual([c.args[1] for c in download.call_args_list], [456])

    def test_command_success_alone_is_not_install_success(self):
        self.install()
        with patch('magicshelf.setup.request_download'), patch('magicshelf.setup.time.monotonic', side_effect=range(0,2000,100)), patch('magicshelf.setup.time.sleep'):
            self.manager.setup.run(self.key, '1.0.0')
        state = self.manager.setup.snapshot(self.meta)
        self.assertFalse(state['ready'])
        self.assertEqual(state['stage'], 'failed')
        self.assertIn('Setup paused', state['error'])
        self.assertGreater(self.manager.setup.jobs[self.key]['retry_at'], 0)

    def test_retry_is_bounded_and_persists_across_restart(self):
        self.install()
        with patch('magicshelf.setup.prepare', side_effect=ValueError('Open Steam, then retry setup.')):
            for attempt in range(3): self.manager.setup.run(self.key, '1.0.0')
        restored = setup.AutomaticSetup(self.manager)
        restored.jobs[self.key]['retry_at'] = 0
        with patch('magicshelf.setup.prepare') as prepare:
            restored.tick()
            prepare.assert_not_called()
        restored.queue(self.key, retry=True)
        self.assertEqual(restored.jobs[self.key]['attempts'], 0)
        restored.jobs[self.key]['stage'] = 'running'
        restored.save()
        self.assertEqual(setup.AutomaticSetup(self.manager).jobs[self.key]['stage'], 'queued')

    def test_repeated_requests_share_one_worker_and_keep_navigation_responsive(self):
        self.install()
        entered, finish = threading.Event(), threading.Event()
        def slow(*args): entered.set(); finish.wait(2)
        with patch('magicshelf.setup.prepare', side_effect=slow) as prepare:
            self.manager.setup.tick()
            self.assertTrue(entered.wait(1))
            for _ in range(3):
                result = self.manager.setup_step(self.key)
                self.manager.setup.tick()
                self.assertFalse(result['busy'])
            self.assertEqual(prepare.call_count, 1)
            finish.set()
            self.manager.setup.thread.join(2)

    def test_removed_or_replaced_creation_cannot_start_old_job(self):
        self.install()
        self.manager.state['modules'][self.key]['version'] = '2.0.0'
        with patch('magicshelf.setup.request_download') as download:
            self.manager.setup.run(self.key, '1.0.0')
            self.manager.setup.tick()
            download.assert_not_called()
            self.assertFalse(self.manager.setup.jobs)

    def test_rpc_rejects_uninstalled_creation_and_undeclared_app(self):
        with self.assertRaises(ValueError): self.manager.setup_step(self.key)
        self.install()
        with self.assertRaises(ValueError): self.manager.setup_step(self.key, 999)
        with self.assertRaises(ValueError): self.manager.setup_open(self.key, 999)
        result = dispatch(self.manager, {'api_version':1, 'method':'module.setup', 'params':{'id':self.key}})
        self.assertEqual(result['modules'][0]['setup']['stage'], 'queued')

    def test_steam_commands_require_running_client_and_numeric_app(self):
        with patch('magicshelf.setup.subprocess.run') as run:
            with self.assertRaises(ValueError): setup.request_download(self.manager.home, 123)
            run.assert_not_called()
            steam = self.manager.home/'.steam'
            steam.mkdir()
            (steam/'steam.pid').write_text(str(os.getpid()))
            setup.request_download(self.manager.home, 123)
            self.assertEqual(run.call_args.args[0], ['steam','-ifrunning','-silent','+app_install','123'])
            self.assertFalse(run.call_args.kwargs.get('shell'))
            for invalid in (True, '123 +quit', 0):
                with self.assertRaises(ValueError): setup.request_download(self.manager.home, invalid)

    def test_cancelled_job_does_not_request_more_downloads(self):
        with patch('magicshelf.setup.request_download') as download:
            setup.prepare(self.meta, self.manager.home, wanted=lambda:False)
            download.assert_not_called()

    def test_invalid_job_file_cannot_stop_the_storefront(self):
        for data in ([], {'bad': {}}, {'bad': {'stage': 'running', 'version': '1.0.0'}}):
            self.manager.setup.path.write_text(json.dumps(data))
            self.assertEqual(setup.AutomaticSetup(self.manager).jobs, {})
