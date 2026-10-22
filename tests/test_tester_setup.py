import hashlib
import io
import json
import shutil
import tarfile
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from magicshelf import setup
from magicshelf.contracts import manifest, machine
from magicshelf.framework_updates import release_for, extract_release, OFFICIAL_RELEASES
from magicshelf.manager import Manager, atomic
from test_framework import FakeSystem, meta


class TesterSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.manager = Manager(self.root/'home', self.root/'run', FakeSystem())
        self.requirement = {'appid': 123, 'title': 'Game support', 'files': ['GameSupport/run']}
        self.meta = {**meta(), 'api_version': 2, 'steam_requirements': [self.requirement], 'minimum_framework_version': '0.3.8'}

    def tearDown(self):
        self.tmp.cleanup()

    def test_fresh_home_shows_setup_then_detects_completed_steam_install(self):
        self.assertFalse(setup.status(self.meta, self.manager.home)['ready'])
        steam = self.manager.home/'.local/share/Steam/steamapps'
        binary = steam/'common/GameSupport/run'; binary.parent.mkdir(parents=True); binary.touch()
        (steam/'appmanifest_123.acf').write_text('"StateFlags" "1026"\n"BytesDownloaded" "40"\n"BytesToDownload" "100"')
        progress = setup.status(self.meta, self.manager.home)
        self.assertFalse(progress['ready']); self.assertEqual(progress['steps'][0]['received_bytes'], 40)
        (steam/'appmanifest_123.acf').write_text('"StateFlags" "4"')
        self.assertTrue(setup.status(self.meta, self.manager.home)['ready'])

    def test_setup_action_is_only_an_installed_manifest_requirement(self):
        with patch('magicshelf.setup.subprocess.run') as run:
            with self.assertRaises(ValueError): setup.open_step(self.meta, self.manager.home, 456)
            run.assert_not_called()
            setup.open_step(self.meta, self.manager.home, 123)
            self.assertEqual(run.call_args.args[0], ['xdg-open', 'steam://install/123'])

    def test_setup_contract_rejects_paths_and_duplicate_ids(self):
        manifest(self.meta)
        for requirements in ([self.requirement, self.requirement], [{**self.requirement, 'files': ['../../private']}], [{**self.requirement, 'appid': '123;command'}]):
            with self.assertRaises(ValueError): manifest({**self.meta, 'steam_requirements': requirements})

    def test_install_request_returns_without_waiting_for_download(self):
        entered, finish = threading.Event(), threading.Event()
        def slow(*args): entered.set(); finish.wait(3)
        with patch.object(self.manager, 'subscribe', side_effect=slow) as subscribe:
            try:
                self.manager.request_install('module.subscribe', {'id': 'org.test.creation', 'subscribed': True, 'permissions': []})
                self.assertTrue(entered.wait(1))
                self.manager.request_install('module.subscribe', {'id': 'org.test.creation', 'subscribed': True, 'permissions': []})
                subscribe.assert_called_once()
            finally:
                finish.set(); self.manager._install_thread.join(4)

    def archive(self, unsafe=False):
        archive = self.root/'update.tar.gz'
        code = b'# fixture installer, never executed\n'
        release = {'version': '1.0.0', 'architecture': machine(), 'files': {'install.py': hashlib.sha256(code).hexdigest()}}
        with tarfile.open(archive, 'w:gz') as tar:
            for name, data in [('magicshelf/install.py', code), ('magicshelf/release.json', json.dumps(release).encode())]:
                info = tarfile.TarInfo(name);info.size = len(data);tar.addfile(info, io.BytesIO(data))
            if unsafe:
                info = tarfile.TarInfo('magicshelf/../../escaped');info.size=1;tar.addfile(info,io.BytesIO(b'x'))
        item = {'url': OFFICIAL_RELEASES+f'download/v1.0.0/magicshelf-1.0.0-linux-{machine()}.tar.gz', 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'size_bytes': archive.stat().st_size}
        return archive, {'schema_version': 1, 'version': '1.0.0', 'artifacts': {machine(): item}}

    def test_framework_update_verifies_archive_and_each_indexed_file(self):
        archive, data = self.archive()
        item = release_for(data, machine())
        source = extract_release(archive, self.root/'verified', item)
        self.assertEqual(json.loads((source/'release.json').read_text())['version'], '1.0.0')
        with self.assertRaises(ValueError): extract_release(archive,self.root/'bad',{**item,'sha256':'0'*64})

    def test_framework_rejects_other_publishers_and_path_escape(self):
        archive, data = self.archive(unsafe=True)
        item = release_for(data, machine())
        with self.assertRaises(ValueError): extract_release(archive,self.root/'bad',item)
        self.assertFalse((self.root/'escaped').exists())
        data['artifacts'][machine()]['url'] = 'https://github.com/other/repo/releases/download/update.tar.gz'
        with self.assertRaises(ValueError): release_for(data,machine())

    def test_framework_download_becomes_ready_and_is_kept_when_offline(self):
        archive, data = self.archive()
        def download(url, path, limit, progress=None):
            if url.endswith('framework.json'): path.write_text(json.dumps(data))
            else: shutil.copy2(archive,path)
        with patch('magicshelf.framework_updates.download', side_effect=download):
            self.manager.framework.check()
        self.assertEqual(self.manager.framework.snapshot()['stage'], 'ready')
        with patch('magicshelf.framework_updates.download', side_effect=TimeoutError()):
            self.manager.framework.check()
        self.assertEqual(self.manager.framework.snapshot()['stage'], 'ready')
        self.assertTrue((self.manager.framework.root/'1.0.0/update.tar.gz').exists())

    def test_interrupted_framework_worker_restores_original_release(self):
        from magicshelf import framework_worker
        old = self.manager.root/'releases/0.3.7'; old.mkdir(parents=True)
        new = self.manager.root/'releases/0.3.8'; new.mkdir()
        (self.manager.root/'current').symlink_to(new)
        source = self.manager.framework.root/'0.3.8/magicshelf';source.mkdir(parents=True)
        atomic(self.manager.framework.path, {'stage': 'installing','version': '0.3.8'})
        atomic(self.manager.root/'framework-install.json', {'previous': str(old),'target':'0.3.8'})
        with patch.object(Path,'home',return_value=self.manager.home), patch.object(framework_worker.subprocess,'run') as run:
            framework_worker.main(source)
        self.assertEqual((self.manager.root/'current').resolve(),old)
        self.assertEqual(self.manager.framework.snapshot()['stage'],'ready')
        self.assertNotIn('steamvr.service',run.call_args.args[0])

    def test_restart_resumes_framework_recovery_without_leaving_ui_locked(self):
        atomic(self.manager.framework.path, {'stage':'installing','version':'1.0.0'})
        self.manager.framework.recover_after_restart()
        self.assertEqual(self.manager.framework.snapshot()['stage'],'ready')
        atomic(self.manager.framework.path, {'stage':'installing','version':'1.0.0'})
        atomic(self.manager.root/'framework-install.json', {'previous':'fixture','target':'1.0.0'})
        with patch.object(self.manager.framework,'spawn_worker') as spawn:
            self.manager.framework.recover_after_restart()
        spawn.assert_called_once_with(self.manager.framework.root/'1.0.0/magicshelf')

    def test_damaged_optional_update_state_does_not_break_the_app(self):
        self.manager.framework.path.write_text('[]')
        self.assertEqual(self.manager.framework.snapshot()['stage'],'idle')
        self.assertEqual(self.manager.snapshot()['framework_update']['stage'],'idle')
