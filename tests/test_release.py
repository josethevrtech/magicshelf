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
        for directory in ("magicshelf","bin","tools","examples","branding"):
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

    def test_recovery_uninstall_icon_pins_standalone_gui_uninstaller(self):
        desktop=(self.root/'dist/Uninstall.MagicShelf.desktop').read_text()
        source=base64.b64decode(re.search("b64decode\\('([^']+)'\\)",desktop)[1]).decode()
        ast.parse(source)
        self.assertIn('/uninstall-magicshelf.py',source)
        self.assertIn("'--gui'",source)
        self.assertIn(hashlib.sha256((self.root/'dist/uninstall-magicshelf.py').read_bytes()).hexdigest(),source)
        self.assertIn('Terminal=false',desktop)
        self.assertIn('Icon=com.josethevrtech.magicshelf',desktop)

    def test_all_download_icons_embed_the_same_public_logo(self):
        for name in ('Install','Uninstall'):
            desktop=(self.root/f'dist/{name}.MagicShelf.desktop').read_text()
            code=base64.b64decode(re.search("b64decode\\('([^']+)'\\)",desktop)[1]).decode()
            encoded=re.search("write_bytes\\(base64.b64decode\\('([^']+)'\\)",code)[1]
            self.assertEqual(base64.b64decode(encoded),(self.root/'build/icon.png').read_bytes())
            self.assertIn('Icon=com.josethevrtech.magicshelf',desktop)
            self.assertNotIn('applications-games',desktop)
        self.assertEqual((self.root/'dist/MagicShelf.png').read_bytes(),(self.root/'build/icon.png').read_bytes())

    def test_release_cannot_pick_up_local_settings_or_build_account_metadata(self):
        for name in ('magicshelf/state.json','magicshelf/private.py','bin/.env','bin/id_rsa'):
            (self.root/name).write_text('PRIVATE TEST DATA MUST NOT SHIP')
        with patch.object(builder,'ROOT',self.root),contextlib.redirect_stdout(io.StringIO()):builder.build('aarch64')
        with tarfile.open(self.root/f'dist/magicshelf-{builder.VERSION}-linux-aarch64.tar.gz') as tar:
            names=tar.getnames()
            for name in ('magicshelf/state.json','magicshelf/private.py','bin/.env','bin/id_rsa'):
                self.assertNotIn('magicshelf/'+name,names)
            for item in tar.getmembers():
                self.assertEqual((item.uid,item.gid,item.uname,item.gname,item.mtime),(0,0,'','',0))

    def test_release_rejects_a_symlink_in_an_approved_source_path(self):
        target=self.root/'magicshelf/client.py';target.unlink();target.symlink_to(self.root/'LICENSE')
        with patch.object(builder,'ROOT',self.root),self.assertRaisesRegex(RuntimeError,'regular file'):
            builder.build('aarch64')

    def test_public_install_link_always_resolves_latest_release(self):
        readme = (PROJECT/'README.md').read_text()
        self.assertIn('https://github.com/josethevrtech/magicshelf/releases/latest/download/Install.MagicShelf.desktop', readme)
        self.assertNotRegex(readme, r'releases/download/v[^/]+/Install\.MagicShelf\.desktop')

if __name__=='__main__':unittest.main()
