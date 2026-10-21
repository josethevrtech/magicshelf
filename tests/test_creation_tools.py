import hashlib
import importlib.util
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from magicshelf.contracts import ContractError
from magicshelf.packages import unpack

ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CreationToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'package'
        (self.source / 'bin').mkdir(parents=True)
        meta = json.loads((ROOT / 'examples/pocket-clock/module.json').read_text())
        (self.source / 'module.json').write_text(json.dumps(meta))
        self.entry = self.source / meta['entrypoint']
        self.entry.write_text('#!/bin/sh\nexit 0\n')
        self.entry.chmod(0o755)
        (self.source / 'LICENSE').write_text('Test fixture')
        self.builder = tool('package_creation')

    def tearDown(self):
        self.temp.cleanup()

    def test_independent_release_installs_and_has_immutable_repository_url(self):
        result = self.builder.build(self.source, self.root / 'dist', 'example/clock')
        item = result['modules'][0]
        archive = next((self.root / 'dist').glob('*.magicshelf'))
        self.assertEqual(item['sha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertIn('/example/clock/releases/download/v' + item['version'] + '/', item['url'])
        self.assertEqual(unpack(archive, self.root / 'installed', item['sha256'], item)['id'], item['id'])
        self.builder.build(self.source, self.root / 'dist', 'example/clock')
        self.entry.write_text('#!/bin/sh\nexit 1\n')
        with self.assertRaisesRegex(ContractError, 'bump'):
            self.builder.build(self.source, self.root / 'dist', 'example/clock')

    def test_rejects_links_and_non_executable_entry(self):
        (self.source / 'leak').symlink_to(ROOT / 'LICENSE')
        with self.assertRaisesRegex(ContractError, 'Links'):
            self.builder.build(self.source, self.root / 'dist', 'example/clock')
        (self.source / 'leak').unlink()
        self.entry.chmod(0o644)
        with self.assertRaisesRegex(ContractError, 'executable'):
            self.builder.build(self.source, self.root / 'dist', 'example/clock')

    def test_sdk_export_has_contracts_and_no_application_or_creation_payload(self):
        archive = tool('build_sdk').build(self.root / 'sdk')
        with tarfile.open(archive) as tar:
            names = tar.getnames()
        self.assertIn('magicshelf-sdk/native/magicshelf_sdk.h', names)
        self.assertIn('magicshelf-sdk/tools/package_creation.py', names)
        self.assertFalse(any('/host.cpp' in p or '/manager.py' in p or '/assets/' in p for p in names))


class LifecycleContractTests(unittest.TestCase):
    def test_api_two_lifecycle_and_legacy_id_use_generic_service(self):
        import sys
        sys.path.insert(0,str(ROOT/'tests'))
        from test_framework import FakeSystem, meta
        from magicshelf.manager import Manager, atomic
        from magicshelf.contracts import manifest
        with tempfile.TemporaryDirectory() as temp:
            manager=Manager(Path(temp)/'home',Path(temp)/'runtime',FakeSystem())
            item=meta();item.update(id='org.magicshelf.android-phone',api_version=2,
                control_entrypoint='bin/control',cleanup_entrypoint='bin/cleanup',
                startup_timeout_sec=120,permissions=['vr-overlay','external-runtime'],memory_mb=2048)
            manifest(item)
            directory=manager.modulepath(item['id'],item['version']);directory.mkdir(parents=True)
            atomic(directory/'module.json',item)
            manager.state['modules'][item['id']]={'version':item['version'],'enabled':False}
            manager.write_unit(item['id'])
            self.assertFalse(manager.is_adapter(item['id']))
            unit=(manager.units/manager.unit(item['id'])).read_text()
            self.assertIn('ExecStopPost=',unit)
            self.assertIn('NoNewPrivileges=no',unit)
            self.assertIn('MAGICSHELF_API_VERSION=2',unit)
            self.assertIn('MAGICSHELF_BACKEND_DATA_DIR=',unit)
            self.assertIn('MemoryMax=2048M',unit)
            item['api_version']=1
            with self.assertRaises(ContractError):manifest(item)

    def test_scaffold_pins_sdk_and_owns_its_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            destination=Path(temp)/'example'
            tool('new_creation').create(destination,'org.example.creation','Example','example/creation','a'*40)
            lock=json.loads((destination/'sdk.lock.json').read_text())
            self.assertEqual(lock['revision'],'a'*40)
            self.assertEqual(json.loads((destination/'module.json').read_text())['id'],'org.example.creation')
            self.assertTrue((destination/'.github/workflows/release.yml').is_file())

if __name__ == "__main__":
    unittest.main()
