import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from magicshelf.contracts import ContractError, catalog, manifest, machine
from magicshelf.manager import ADAPTERS, Manager, System, atomic
from magicshelf.packages import check_url, unpack
from magicshelf.server import dispatch

def meta(ver="1.0.0"):
    return {"schema_version": 1, "api_version": 1, "id": "org.test.toy", "version": ver, "name": "Test toy", "description": "A test", "author": "Test", "license": "MIT", "platform": "linux", "architecture": machine(), "entrypoint": "bin/toy", "permissions": ["vr-overlay"], "memory_mb": 64}

def package(path, data=None, extra=None):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("module.json", json.dumps(data or meta()))
        info = zipfile.ZipInfo("bin/toy")
        info.external_attr = 0o100755 << 16
        z.writestr(info, "#!/bin/sh\nexit 0\n")
        if extra:
            z.writestr(*extra)
    return hashlib.sha256(path.read_bytes()).hexdigest()

class FakeSystem:
    def __init__(self):
        self.calls = []
        self.running = set()
        self.frozen = set()
        self.paused_containers = set()
    def call(self, *args, **kwargs):
        self.calls.append(args)
        if args[0] == "start":
            self.running.update(args[1:])
        if args[0] == "stop" or (args[0] == "disable" and "--now" in args):
            self.running.difference_update(args[1:])
        if args[0] == "freeze":
            self.frozen.update(args[1:])
        if args[0] == "thaw":
            self.frozen.difference_update(args[1:])
    def active(self, unit):
        return unit in self.running
    def pause_container(self, name, paused):
        self.calls.append(("pause-container", name, paused))
        if paused:
            self.paused_containers.add(name)
        else:
            self.paused_containers.discard(name)

class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.home = self.path / "home"
        self.home.mkdir()
        self.system = FakeSystem()
        self.manager = Manager(self.home, self.path / "runtime", self.system)
    def tearDown(self):
        self.temp.cleanup()

    def adapter(self, key, enabled=True):
        self.manager.legacy.mkdir(parents=True, exist_ok=True)
        (self.manager.legacy / "magicshelf-api-version").write_text("2")
        self.manager.state["modules"][key] = {"version":"0.1.0", "enabled":enabled, "adapter":True}
        unit = self.manager.unit(key)
        self.system.running.update([unit, "steamvr.service", *ADAPTERS[key]["backends"]])
        return unit

    def test_adapter_toggle_pauses_runtime_keeps_capture_and_redocks(self):
        key = "org.magicshelf.android-phone"
        unit = self.adapter(key)
        with patch("magicshelf.manager.subprocess.run") as run:
            result = self.manager.toggle(key, False)
            self.assertTrue(self.system.active(unit))
            self.assertFalse(result["modules"][0]["running"])
            self.assertEqual(self.system.frozen, set(ADAPTERS[key]["backends"]))
            self.assertEqual(self.system.paused_containers, {"lepton-courage-tablet"})
            self.assertIn(("disable", unit, *ADAPTERS[key]["backends"]), self.system.calls)
            self.assertEqual(run.call_args.args[0][-1], "--hide")
            self.manager.reconcile()
            self.assertTrue(self.system.active(unit))
            self.assertEqual(self.system.frozen, set(ADAPTERS[key]["backends"]))
            self.manager.toggle(key, True)
            self.assertFalse(self.system.frozen)
            self.assertFalse(self.system.paused_containers)
            self.assertEqual(run.call_args.args[0][-1], "--dock")
        self.assertNotIn(("disable", "--now", unit), self.system.calls)
        self.assertNotIn(("start", unit), self.system.calls)

    def test_digivice_off_does_not_pause_phone_or_other_apps(self):
        phone = "org.magicshelf.android-phone"
        pet = "org.magicshelf.digital-partner"
        self.adapter(phone)
        self.adapter(pet)
        with patch("magicshelf.manager.subprocess.run"):
            self.manager.toggle(pet, False)
        self.assertEqual(self.system.frozen, {"digitalpartner.service"})
        self.assertFalse(self.system.paused_containers)
        self.assertTrue(self.manager.state["modules"][phone]["enabled"])

    def test_resume_after_manager_restart_does_not_move_enabled_creation(self):
        key = "org.magicshelf.android-phone"
        self.adapter(key)
        self.system.frozen.update(ADAPTERS[key]["backends"])
        self.system.paused_containers.add("lepton-courage-tablet")
        self.manager.save()
        restored = Manager(self.home, self.path / "runtime", self.system)
        with patch("magicshelf.manager.subprocess.run") as run:
            restored.reconcile()
        self.assertFalse(self.system.frozen)
        self.assertFalse(self.system.paused_containers)
        run.assert_not_called()

    def test_off_reconciliation_works_without_capture_shell(self):
        key = "org.magicshelf.android-phone"
        unit = self.adapter(key, False)
        self.system.running.remove(unit)
        with patch("magicshelf.manager.subprocess.run") as run:
            self.manager.reconcile()
        self.assertEqual(self.system.frozen, set(ADAPTERS[key]["backends"]))
        self.assertEqual(self.system.paused_containers, {"lepton-courage-tablet"})
        run.assert_not_called()

    def test_failed_off_restores_enabled_execution(self):
        key = "org.magicshelf.android-phone"
        self.adapter(key)
        pause = self.system.pause_container
        def fail_pause(name, paused):
            if paused:
                raise RuntimeError("container pause failed")
            pause(name, paused)
        with patch.object(self.system, "pause_container", side_effect=fail_pause), patch("magicshelf.manager.subprocess.run"), self.assertRaisesRegex(RuntimeError, "container pause failed"):
            self.manager.toggle(key, False)
        self.assertTrue(self.manager.state["modules"][key]["enabled"])
        self.assertFalse(self.system.frozen)

    def test_failed_on_returns_to_paused_state(self):
        key = "org.magicshelf.android-phone"
        self.adapter(key, False)
        def command(args, **kwargs):
            if args[-1] == "--dock":
                raise RuntimeError("dock failed")
        with patch("magicshelf.manager.subprocess.run", side_effect=command), self.assertRaisesRegex(RuntimeError, "dock failed"):
            self.manager.toggle(key, True)
        self.assertFalse(self.manager.state["modules"][key]["enabled"])
        self.assertEqual(self.system.frozen, set(ADAPTERS[key]["backends"]))
        self.assertEqual(self.system.paused_containers, {"lepton-courage-tablet"})

    def test_phone_off_does_not_pause_digivice(self):
        phone = "org.magicshelf.android-phone"
        pet = "org.magicshelf.digital-partner"
        self.adapter(phone)
        self.adapter(pet)
        with patch("magicshelf.manager.subprocess.run"):
            self.manager.toggle(phone, False)
        self.assertEqual(self.system.frozen, set(ADAPTERS[phone]["backends"]))
        self.assertTrue(self.manager.state["modules"][pet]["enabled"])

    def test_container_operations_are_scoped_and_idempotent(self):
        name = "lepton-courage-tablet"
        container = {"Names": [name], "Labels": {"lepton": "true"}, "Id": "exact-container-id", "State": "running"}
        unrelated = {**container, "Names": [name + "-other"], "Id": "other"}
        for state, paused, operation in [("running", True, "pause"), ("paused", True, None), ("paused", False, "unpause"), ("running", False, None), ("exited", True, None)]:
            with self.subTest(state=state, paused=paused), patch("magicshelf.manager.subprocess.run") as run:
                run.return_value.stdout = json.dumps([unrelated, {**container, "State": state}])
                System().pause_container(name, paused)
                self.assertEqual(run.call_count, 2 if operation else 1)
                if operation:
                    self.assertEqual(run.call_args.args[0], ["podman", operation, "exact-container-id"])
        with patch("magicshelf.manager.subprocess.run") as run:
            run.return_value.stdout = "[]"
            System().pause_container(name, True)
            self.assertEqual(run.call_count, 1)

    def test_container_inspection_failure_is_not_silent_success(self):
        with patch("magicshelf.manager.subprocess.run", side_effect=subprocess.CalledProcessError(125, "podman")), self.assertRaises(subprocess.CalledProcessError):
            System().pause_container("lepton-courage-tablet", True)

    def test_supported_contract(self):
        self.assertEqual(manifest(meta())["api_version"], 1)

    def test_reject_incompatible_modules_before_install(self):
        for key, value in [("api_version", 3), ("schema_version", True), ("entrypoint", "../run"), ("permissions", ["root"]), ("architecture", "any"), ("version", "latest"), ("memory_mb", 4096)]:
            with self.subTest(key=key):
                item = meta();item[key] = value
                with self.assertRaises(ContractError):
                    manifest(item)

    def test_url_pinning(self):
        check_url("https://github.com/author/toys/releases/download/v1/toy.magicshelf")
        for url in ["http://github.com/a", "https://localhost/a", "file:///tmp/toy", "https://github.com.attacker.test/a", "https://user@github.com/a", "https://github.com:444/a"]:
            with self.subTest(url=url), self.assertRaises(ContractError):
                check_url(url)

    def test_good_package(self):
        archive = self.path / "toy.zip";digest = package(archive)
        result = unpack(archive, self.path / "unpacked", digest, meta())
        self.assertEqual(result["id"], "org.test.toy")
        self.assertTrue(os.access(self.path / "unpacked/bin/toy", os.X_OK))

    def test_checksum_mismatch_makes_no_install(self):
        archive = self.path / "toy.zip";package(archive)
        with self.assertRaises(ContractError):
            unpack(archive, self.path / "unpacked", "0" * 64)
        self.assertFalse((self.path / "unpacked").exists())

    def test_zip_traversal_is_rejected(self):
        archive = self.path / "toy.zip";digest = package(archive, extra=("../escaped", "bad"))
        with self.assertRaises(ContractError):
            unpack(archive, self.path / "unpacked", digest)
        self.assertFalse((self.path / "escaped").exists())

    def test_zip_symlink_is_rejected(self):
        archive = self.path / "toy.zip";package(archive)
        with zipfile.ZipFile(archive, "a") as z:
            info = zipfile.ZipInfo("link");info.external_attr = 0o120777 << 16;z.writestr(info, "/etc/passwd")
        with self.assertRaises(ContractError):
            unpack(archive, self.path / "unpacked", hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_catalog_cannot_lie_about_permissions(self):
        archive = self.path / "toy.zip";digest = package(archive)
        expected = meta();expected["permissions"] = ["vr-overlay", "network"]
        with self.assertRaises(ContractError):
            unpack(archive, self.path / "unpacked", digest, expected)

    def test_catalog_supports_architecture_variants(self):
        first = {**meta(), "url": "https://github.com/a/b", "sha256": "0"*64, "size_bytes": 1}
        second = {**first, "architecture": "aarch64" if machine() == "x86_64" else "x86_64"}
        catalog({"schema_version": 1, "name": "Tests", "modules": [first, second]})
        with self.assertRaises(ContractError):
            catalog({"schema_version": 1, "name": "Tests", "modules": [first, first]})

    def stage(self, ver):
        archive = self.path / (ver + ".zip");digest = package(archive, meta(ver));directory = self.path / (ver + "-stage");unpack(archive, directory, digest);return directory

    def test_install_does_not_enable_toy(self):
        self.manager.commit_package("org.test.toy", "1.0.0", self.stage("1.0.0"))
        self.assertFalse(self.manager.state["modules"]["org.test.toy"]["enabled"])
        self.assertEqual(json.loads(self.manager.layoutpath.read_text())["objects"], [])

    def test_update_failure_restores_version_and_data(self):
        key = "org.test.toy";self.manager.commit_package(key, "1.0.0", self.stage("1.0.0"))
        self.manager.state["modules"][key]["enabled"] = True
        data = self.manager.root / "module-data" / key;data.mkdir(parents=True);(data / "save").write_text("original")
        def start(module):
            if self.manager.state["modules"][module]["version"] == "2.0.0":
                (data / "save").write_text("changed by broken update")
                raise RuntimeError("readiness failed")
        with patch.object(self.manager, "start", side_effect=start), self.assertRaises(RuntimeError):
            self.manager.commit_package(key, "2.0.0", self.stage("2.0.0"))
        self.assertEqual(self.manager.state["modules"][key]["version"], "1.0.0")
        self.assertTrue(self.manager.state["modules"][key]["enabled"])
        self.assertEqual((data / "save").read_text(), "original")
        self.assertFalse(self.manager.modulepath(key, "2.0.0").exists())

    def test_remove_keeps_saved_data(self):
        key = "org.test.toy";self.manager.commit_package(key, "1.0.0", self.stage("1.0.0"))
        data = self.manager.root / "module-data" / key;data.mkdir(parents=True);(data / "save").write_text("keep")
        self.manager.remove(key)
        self.assertEqual((data / "save").read_text(), "keep")
        self.assertNotIn(key, self.manager.state["modules"])

    def test_manual_rollback_recovers_previous_save(self):
        key = "org.test.toy";self.manager.commit_package(key, "1.0.0", self.stage("1.0.0"))
        data = self.manager.root / "module-data" / key;data.mkdir(parents=True);(data / "save").write_text("before")
        self.manager.commit_package(key, "2.0.0", self.stage("2.0.0"))
        (data / "save").write_text("after")
        self.manager.rollback(key)
        self.assertEqual(self.manager.state["modules"][key]["version"], "1.0.0")
        self.assertEqual((data / "save").read_text(), "before")

    def test_failed_checkpoint_does_not_replace_original_data(self):
        key = "org.test.toy";self.manager.commit_package(key, "1.0.0", self.stage("1.0.0"))
        data = self.manager.root / "module-data" / key;data.mkdir(parents=True);(data / "save").write_text("original")
        staged = self.stage("2.0.0")
        def fail_copy(source, target, **kwargs):
            target.mkdir(parents=True)
            (target / "partial").write_text("incomplete backup")
            raise OSError("disk full")
        with patch("magicshelf.manager.shutil.copytree", side_effect=fail_copy), self.assertRaises(OSError):
            self.manager.commit_package(key, "2.0.0", staged)
        self.assertEqual((data / "save").read_text(), "original")
        self.assertEqual(self.manager.state["modules"][key]["version"], "1.0.0")

    def test_session_survives_manager_restart(self):
        key = "org.test.toy";self.manager.commit_package(key, "1.0.0", self.stage("1.0.0"))
        self.manager.write_unit(key)
        token = self.manager.sessions[key]
        restored = Manager(self.home, self.path / "runtime", self.system)
        dispatch(restored, {"api_version":1,"method":"runtime.ready","params":{"id":key,"token":token}})
        self.assertIn(key, restored.ready)

    @unittest.skipUnless(shutil.which("systemd-analyze"), "systemd verifier is not available")
    def test_generated_unit_passes_the_real_systemd_parser(self):
        key = "org.test.toy";self.manager.commit_package(key, "1.0.0", self.stage("1.0.0"))
        self.manager.write_unit(key)
        for name in ("steamvr.service", "magicshelf.service"):
            (self.manager.units / name).write_text("[Service]\nExecStart=/bin/true\n")
        env = os.environ.copy();env["SYSTEMD_UNIT_PATH"] = str(self.manager.units) + ":/usr/lib/systemd/user"
        result = subprocess.run(["systemd-analyze", "--user", "verify", "--man=no", str(self.manager.units / self.manager.unit(key))], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_disabled_toy_loses_its_slot(self):
        key = "org.test.toy";self.manager.commit_package(key, "1.0.0", self.stage("1.0.0"))
        self.manager.toggle(key, True)
        self.assertEqual(json.loads(self.manager.layoutpath.read_text())["objects"], ["magicshelf.module." + key])
        self.manager.toggle(key, False)
        self.assertEqual(json.loads(self.manager.layoutpath.read_text())["objects"], [])

    def test_readiness_session_cannot_be_spoofed(self):
        self.manager.sessions["org.test.toy"] = "expected"
        with self.assertRaises(ValueError):
            dispatch(self.manager, {"api_version":1,"method":"runtime.ready","params":{"id":"org.test.toy","token":"wrong"}})
        dispatch(self.manager, {"api_version":1,"method":"runtime.ready","params":{"id":"org.test.toy","token":"expected"}})
        self.assertIn("org.test.toy", self.manager.ready)

    def test_unknown_api_cannot_mutate_state(self):
        before = copy.deepcopy(self.manager.state)
        with self.assertRaises(ValueError):
            dispatch(self.manager, {"api_version":2,"method":"modules.adopt"})
        self.assertEqual(before, self.manager.state)

    def test_adoption_requires_a_migrated_local_installation(self):
        with self.assertRaises(ContractError):
            self.manager.adopt()
        self.manager.legacy.mkdir(parents=True)
        (self.manager.legacy / "magicshelf-api-version").write_text("1\n")
        for name in ("digitalpartner-vr", "android-phone-vr"):
            (self.manager.legacy / name).touch()
        self.manager.adopt()
        self.assertEqual(len(self.manager.state["modules"]), 2)

    def test_missing_module_files_do_not_break_the_library(self):
        key = "org.test.toy";self.manager.commit_package(key, "1.0.0", self.stage("1.0.0"))
        (self.manager.modulepath(key, "1.0.0") / "module.json").unlink()
        self.manager.state["catalog"] = [meta("2.0.0")]
        snapshot = self.manager.snapshot()
        self.assertTrue(snapshot["modules"][0]["broken"])
        self.assertEqual(snapshot["modules"][0]["update"]["version"], "2.0.0")

    def test_other_collection_cannot_replace_existing_toy(self):
        self.manager.commit_package("org.test.toy", "1.0.0", self.stage("1.0.0"), "https://github.com/owner/catalog")
        self.manager.state["catalog"] = [{**meta("2.0.0"), "catalog_url": "https://github.com/other/catalog"}]
        with self.assertRaises(ContractError):
            self.manager.install("org.test.toy", ["vr-overlay"])

if __name__ == "__main__":
    unittest.main()
