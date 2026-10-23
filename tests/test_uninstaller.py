import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('uninstaller', Path(__file__).resolve().parents[1]/'uninstall.py')
uninstaller = importlib.util.module_from_spec(spec); spec.loader.exec_module(uninstaller)


class UninstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.home = Path(self.temp.name)
        self.units = self.home/'.config/systemd/user'; self.units.mkdir(parents=True)
        self.config = self.home/'.config/magicshelf'; self.config.mkdir()
        self.root = self.home/'.local/share/magicshelf'; self.root.mkdir(parents=True)
        self.desktop = self.home/'Desktop'; self.desktop.mkdir()
        self.orphan = 'magicshelf-module-org.magicshelf.orphan.service'
        self.running = {'magicshelf.service', 'magicshelf-vr.service', self.orphan}
        self.calls = []; self.refuse = None
        for name in ('magicshelf.service', 'magicshelf-vr.service'):
            (self.units/name).write_text('unit')
            target = self.units/'default.target.wants'; target.mkdir(exist_ok=True)
            (target/name).symlink_to(self.units/name)
        (self.desktop/'MagicShelf.desktop').write_text('shortcut')
        (self.desktop/'Uninstall MagicShelf.desktop').write_text('uninstall')
        (self.desktop/'Install.MagicShelf.desktop').write_text('keep installer')
        (self.root/'module-data').mkdir(); (self.root/'module-data/save').write_bytes(b'saved game')
        (self.config/'state.json').write_text(json.dumps({'modules':{'test':{'enabled':True,'subscribed':True}}}))
        def system(*args, **kwargs):
            self.calls.append(args); output = ''
            if args[0] == 'show':
                active = args[1] in self.running
                loaded = active or (self.units/args[1]).exists()
                output = f'LoadState={"loaded" if loaded else "not-found"}\nActiveState={"active" if active else "inactive"}\nMainPID={123 if active else 0}\n'
            elif args[0] == 'stop' and args[1] != self.refuse: self.running.discard(args[1])
            elif args[0] == 'list-units': output = self.orphan+' loaded active running orphan\n'
            return types.SimpleNamespace(returncode=0, stdout=output, stderr='')
        self.patches = [patch.object(Path,'home',return_value=self.home), patch.object(uninstaller.os,'geteuid',return_value=1000), patch.object(uninstaller,'system',side_effect=system), patch.object(uninstaller,'desktop_directory',return_value=self.desktop)]
        for p in self.patches: p.start()
    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()
    def remove(self):
        with contextlib.redirect_stdout(io.StringIO()): uninstaller.uninstall()
    def test_partial_uninstall_stops_loaded_orphan_without_state_entry(self):
        (self.units/'magicshelf.service').unlink()
        self.remove()
        self.assertFalse(self.running)
        self.assertFalse(list(self.units.glob('*.wants/magicshelf*')))
        self.assertFalse((self.desktop/'MagicShelf.desktop').exists())
        self.assertFalse((self.desktop/'Uninstall MagicShelf.desktop').exists())
        self.assertTrue((self.desktop/'Install.MagicShelf.desktop').exists())
        self.assertEqual((self.root/'module-data/save').read_bytes(),b'saved game')
        state=json.loads((self.config/'state.json').read_text())['modules']['test']
        self.assertFalse(state['enabled']); self.assertTrue(state['subscribed'])
        self.assertFalse(any(call[0]=='restart' for call in self.calls))
    def test_repeated_uninstall_succeeds_without_missing_file_errors(self):
        self.remove(); self.remove()
        self.assertTrue((self.root/'uninstalled').exists())
    def test_stop_failure_keeps_shortcuts_and_unit_files(self):
        self.refuse='magicshelf.service'
        with self.assertRaisesRegex(RuntimeError,'still running'): self.remove()
        self.assertTrue((self.units/'magicshelf.service').exists())
        self.assertTrue((self.desktop/'MagicShelf.desktop').exists())
    def test_unavailable_user_bus_does_not_claim_success_or_remove_files(self):
        with patch.object(uninstaller,'system',return_value=types.SimpleNamespace(returncode=1,stdout='',stderr='Failed to connect to bus')):
            with self.assertRaisesRegex(RuntimeError,'desktop session'): self.remove()
        self.assertFalse((self.root/'uninstalled').exists())
        self.assertTrue((self.units/'magicshelf.service').exists())
    def test_corrupt_saved_settings_do_not_prevent_uninstall_or_get_overwritten(self):
        (self.config/'state.json').write_text('corrupt original')
        self.remove()
        self.assertEqual((self.config/'state.json').read_text(),'corrupt original')
    def test_running_installer_prevents_concurrent_removal(self):
        import fcntl
        with (self.root/'install.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError,'finishing an update'): self.remove()
        self.assertTrue(self.running)
    def test_cancelled_desktop_uninstall_changes_nothing(self):
        with patch.object(uninstaller.shutil,'which',return_value='/usr/bin/kdialog'), patch.object(uninstaller.subprocess,'run',return_value=types.SimpleNamespace(returncode=1)):
            self.assertEqual(uninstaller.main(['--gui']),0)
        self.assertFalse((self.root/'uninstalled').exists())
        self.assertTrue(self.running)
    def test_sudo_is_rejected_before_touching_user_files(self):
        with patch.object(uninstaller.os,'geteuid',return_value=0):
            with self.assertRaisesRegex(RuntimeError,'own desktop'): self.remove()
        self.assertTrue(self.running)


if __name__=='__main__': unittest.main()
