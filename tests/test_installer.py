import hashlib
import importlib.util
import json
import platform
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("magicshelf_installer", Path(__file__).resolve().parents[1] / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home";self.home.mkdir();(self.home / "Desktop").mkdir()
        self.source = self.root / "source";self.source.mkdir();(self.source / "bin").mkdir()
        for name in ("magicshelf", "magicshelf-bootstrap", "magicshelf-vr"):
            path = self.source / "bin" / name;path.write_text("#!/bin/sh\nexit 0\n");path.chmod(0o755)
        self.meta = {"version":"0.1.0","architecture":platform.machine(),"files":{str(p.relative_to(self.source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.rglob("*") if p.is_file()}}
        (self.source / "release.json").write_text(json.dumps(self.meta))
        self.calls = []
        def system(*args, **kwargs):
            self.calls.append(args)
            return types.SimpleNamespace(returncode=1 if args[0]=="is-active" else 0)
        self.original_is_file = Path.is_file
        self.patches = [patch.object(Path,"home",return_value=self.home), patch.object(Path,"is_file",lambda p: True if str(p).startswith("/opt/steamvr/") else self.original_is_file(p)), patch.object(installer,"system",side_effect=system), patch("magicshelf.client.request",return_value={"api_version":1,"version":"0.1.0"})]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def test_user_install_creates_shortcut_without_restart_of_steamvr(self):
        with patch.object(installer.subprocess,"run",return_value=types.SimpleNamespace(returncode=0)):
            installer.install(self.source)
        self.assertTrue((self.home / "Desktop/MagicShelf.desktop").exists())
        self.assertTrue((self.home / ".local/share/magicshelf/current").is_symlink())
        self.assertFalse(any("steamvr.service" in call and call[0]=="restart" for call in self.calls))
        self.assertTrue(all("sudo" not in call for call in self.calls))
    def test_tampered_release_is_rejected_before_writing_integration(self):
        (self.source / "bin/magicshelf").write_text("tampered")
        with self.assertRaises(RuntimeError):installer.install(self.source)
        self.assertFalse((self.home / ".config/systemd/user/magicshelf.service").exists())
    def test_first_install_failure_stops_new_services_and_removes_current(self):
        with patch.object(installer.subprocess,"run",side_effect=RuntimeError("bootstrap failed")), self.assertRaises(RuntimeError):
            installer.install(self.source)
        self.assertFalse((self.home / ".local/share/magicshelf/current").exists())
        self.assertIn(("disable","--now","magicshelf-vr.service","magicshelf.service"),self.calls)
        self.assertFalse((self.home / ".config/systemd/user/magicshelf.service").exists())
    def test_new_dashboard_must_render_before_update_is_accepted(self):
        root = self.home / '.local/share/magicshelf';root.mkdir(parents=True)
        old = root / 'releases/0.0.1';old.mkdir(parents=True)
        (root / 'current').symlink_to(old)
        def system(*args, **kwargs):
            self.calls.append(args)
            return types.SimpleNamespace(returncode=0,stdout='123\n')
        with patch.object(installer,'system',side_effect=system),patch.object(installer.time,'sleep'),patch.object(installer.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)):
            with self.assertRaisesRegex(RuntimeError,'could not open'):
                installer.install(self.source)
        self.assertEqual((root/'current').resolve(),old)
        self.assertFalse(any('steamvr.service' in call and call[0]=='restart' for call in self.calls))

    def test_failed_framework_update_restores_previous_release_and_units(self):
        root = self.home / ".local/share/magicshelf";root.mkdir(parents=True)
        old = root / "releases/0.0.1";old.mkdir(parents=True)
        (root / "current").symlink_to(old)
        units = self.home / ".config/systemd/user";units.mkdir(parents=True)
        (units / "magicshelf.service").write_text("old service")
        with patch.object(installer.subprocess,"run",side_effect=RuntimeError("bootstrap failed")), self.assertRaises(RuntimeError):
            installer.install(self.source)
        self.assertEqual((root / "current").resolve(),old)
        self.assertEqual((units / "magicshelf.service").read_text(),"old service")

if __name__ == "__main__":unittest.main()
