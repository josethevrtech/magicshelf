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
        for name in ("shelf.json","install.py","uninstall.py","LICENSE","OPENVR-LICENSE.txt"):
            shutil.copy2(PROJECT / name,self.root / name)
        for name in ("build/bin/magicshelf-vr","build/modules/pocket-clock/bin/pocket-clock","build/icon.png"):
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
    def test_catalog_matches_download_artifact(self):
        self.assertEqual(json.loads((self.root/'dist/catalog.json').read_text())['modules'],[])
        data=json.loads((self.root/'dist/example-catalog.json').read_text());item=data['modules'][0]
        artifact=next((self.root/'dist').glob('*.magicshelf'))
        self.assertEqual(item['sha256'],hashlib.sha256(artifact.read_bytes()).hexdigest())
        self.assertEqual(item['size_bytes'],artifact.stat().st_size)
        with zipfile.ZipFile(artifact) as z:self.assertEqual(json.loads(z.read('module.json'))['id'],item['id'])

if __name__=='__main__':unittest.main()
