import ast
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import re
import shutil
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_builder", PROJECT / "tools/build_release.py")
builder = importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.root = Path(self.temp.name)
        for directory in ("magicshelf","bin","tools","examples"):
            shutil.copytree(PROJECT / directory, self.root / directory, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("catalog.json","collections.json","shelf.json","install.py","uninstall.py","LICENSE","OPENVR-LICENSE.txt"):
            shutil.copy2(PROJECT / name,self.root / name)
        for name in ("build/bin/magicshelf-vr","build/icon.png"):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b"Packaging fixture only; not a binary release");path.chmod(0o755)
        with patch.object(builder,"ROOT",self.root),contextlib.redirect_stdout(io.StringIO()):builder.build("aarch64")
    def tearDown(self):self.temp.cleanup()
    def test_archive_file_index_and_bundled_package_match(self):
        archive=self.root/('dist/magicshelf-'+builder.VERSION+'-linux-aarch64.tar.gz')
        with tarfile.open(archive) as tar:
            release=json.load(tar.extractfile('magicshelf/release.json'))
            for name,digest in release['files'].items():self.assertEqual(hashlib.sha256(tar.extractfile('magicshelf/'+name).read()).hexdigest(),digest)
            self.assertEqual(release['bundled'],[])
    def test_desktop_launcher_pins_bootstrap_without_assert(self):
        desktop=(self.root/'dist/Install.MagicShelf.desktop').read_text()
        encoded=re.search("b64decode\\('([^']+)'\\)",desktop)[1]
        source=base64.b64decode(encoded).decode()
        ast.parse(source)
        self.assertNotIn('assert ',source)
        expected=hashlib.sha256((self.root/'dist/install-magicshelf.py').read_bytes()).hexdigest()
        self.assertIn(expected,source)
        self.assertNotIn('@BOOTSTRAP',source)
    def test_graphical_installer_and_update_manifest_are_pinned_to_same_archive(self):
        from magicshelf.framework_updates import release_for
        data=json.loads((self.root/'dist/framework.json').read_text())
        item=release_for(data,'aarch64')
        archive=self.root/('dist/magicshelf-'+builder.VERSION+'-linux-aarch64.tar.gz')
        self.assertEqual(item['sha256'],hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(item['size_bytes'],archive.stat().st_size)
        self.assertIn('Terminal=false',(self.root/'dist/Install.MagicShelf.desktop').read_text())
        ast.parse((self.root/'dist/install-magicshelf.py').read_text())

    def test_framework_release_does_not_build_or_bundle_creations(self):
        self.assertEqual((self.root/'dist/catalog.json').read_bytes(), (PROJECT/'catalog.json').read_bytes())
        self.assertEqual(list((self.root/'dist').glob('*.magicshelf')), [])
        self.assertFalse((self.root/'dist/example-catalog.json').exists())

if __name__=='__main__':unittest.main()
