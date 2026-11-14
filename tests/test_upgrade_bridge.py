import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = ROOT / "upgrade_bridge_2_0_1_to_2_1_0.py"
SPEC = importlib.util.spec_from_file_location("upgrade_bridge", BRIDGE_PATH)
BRIDGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BRIDGE)


def published_release():
    raw = (ROOT / "update" / "manifest.json").read_bytes()
    return BRIDGE.validate_manifest(raw)


def published_archive():
    return (ROOT / "global-home-nodes-v2.1.0.zip").read_bytes()


def rewrite_archive(raw, transform):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            name, data = transform(info.filename, source.read(info))
            target.writestr(name, data)
    return output.getvalue()


class UpgradeBridgeTests(unittest.TestCase):
    def test_reproduces_201_to_210_rejection_and_bridge_accepts_exact_13_files(self):
        old_zip = ROOT / "global-home-nodes-v2.0.1.zip"
        with zipfile.ZipFile(old_zip) as archive:
            old_source = archive.read("global-home-nodes/update_manager.py")
        legacy = {"__name__": "legacy_v201_updater"}
        exec(compile(old_source, "update_manager.py", "exec"), legacy)
        release = published_release()
        package_bytes = published_archive()

        self.assertEqual(len(legacy["PACKAGE_FILES"]), 11)
        with self.assertRaisesRegex(RuntimeError, "源码ZIP损坏或不符合安全格式"):
            legacy["_archive_files"](package_bytes, release)

        files = BRIDGE.validate_archive(package_bytes, release)
        self.assertEqual(set(files), BRIDGE.PACKAGE_FILES)
        self.assertEqual(len(files), 13)
        self.assertIn("gl", files)
        self.assertIn("relay_export.py", files)

    def test_rejects_a_manifest_that_does_not_match_the_pinned_release(self):
        manifest = json.loads((ROOT / "update" / "manifest.json").read_text(encoding="utf-8"))
        manifest["archive_sha256"] = "0" * 64
        with self.assertRaises(BRIDGE.UpgradeError):
            BRIDGE.validate_manifest(json.dumps(manifest).encode("utf-8"))

    def test_rejects_traversal_and_duplicate_archive_members(self):
        raw = published_archive()
        release = published_release()

        traversal = rewrite_archive(
            raw,
            lambda name, data: ("global-home-nodes/../escape" if name.endswith("/gl") else name, data),
        )
        traversal_release = dict(release, archive_sha256=hashlib.sha256(traversal).hexdigest())
        with self.assertRaises(BRIDGE.UpgradeError):
            BRIDGE.validate_archive(traversal, traversal_release)

        duplicate = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(duplicate, "w", zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                target.writestr(info.filename, source.read(info))
            target.writestr("global-home-nodes/gl", b"duplicate")
        duplicate_bytes = duplicate.getvalue()
        duplicate_release = dict(release, archive_sha256=hashlib.sha256(duplicate_bytes).hexdigest())
        with self.assertRaises(BRIDGE.UpgradeError):
            BRIDGE.validate_archive(duplicate_bytes, duplicate_release)

    def test_rejects_tampered_member_even_when_outer_hash_is_updated(self):
        raw = published_archive()
        release = published_release()
        tampered = rewrite_archive(
            raw,
            lambda name, data: (name, data + b"# modified") if name.endswith("/gl") else (name, data),
        )
        changed_release = dict(release, archive_sha256=hashlib.sha256(tampered).hexdigest())
        with self.assertRaisesRegex(BRIDGE.UpgradeError, "SHA256"):
            BRIDGE.validate_archive(tampered, changed_release)

    def test_installs_gl_and_relay_export_without_touching_node_state_or_services(self):
        release = published_release()
        files = BRIDGE.validate_archive(published_archive(), release)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "opt" / "global-home-nodes"
            app.mkdir(parents=True)
            (app / "INSTALLER-MARKER").write_text("global-home-nodes-v2\n", encoding="utf-8")
            (app / "VERSION.json").write_text('{"version":"2.0.1","adapter_version":"1.0.0"}\n', encoding="utf-8")
            (app / "update_manager.py").write_text("legacy updater\n", encoding="utf-8")
            (app / "operator-notes.txt").write_text("preserve me\n", encoding="utf-8")
            config = root / "etc" / "global-home-nodes" / "current" / "state.private.json"
            config.parent.mkdir(parents=True)
            config.write_text("existing node state\n", encoding="utf-8")
            service = root / "etc" / "init.d" / "global-home-nodes"
            service.parent.mkdir(parents=True)
            service.write_text("existing service\n", encoding="utf-8")
            gl_link = root / "usr" / "local" / "bin" / "gl"
            backup = root / "root" / "global-home-nodes-code-backups"

            BRIDGE.install_verified_files(files, app, gl_link, backup)

            self.assertEqual(json.loads((app / "VERSION.json").read_text())["version"], "2.1.0")
            self.assertTrue((app / "relay_export.py").is_file())
            self.assertTrue(os.access(app / "gl", os.X_OK))
            self.assertTrue(gl_link.is_symlink())
            self.assertEqual(os.readlink(gl_link), str(app / "gl"))
            self.assertEqual((app / "operator-notes.txt").read_text(), "preserve me\n")
            self.assertEqual(config.read_text(), "existing node state\n")
            self.assertEqual(service.read_text(), "existing service\n")
            self.assertTrue(list(backup.glob("*/update_manager.py")))

    def test_rejects_non_201_install_without_writing(self):
        files = BRIDGE.validate_archive(published_archive(), published_release())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "app"
            app.mkdir()
            (app / "INSTALLER-MARKER").write_text("global-home-nodes-v2\n", encoding="utf-8")
            version = app / "VERSION.json"
            version.write_text('{"version":"2.0.2","adapter_version":"1.0.0"}\n', encoding="utf-8")
            before = version.read_bytes()
            gl_link = root / "usr" / "local" / "bin" / "gl"
            with self.assertRaisesRegex(BRIDGE.UpgradeError, "2.0.1"):
                BRIDGE.install_verified_files(files, app, gl_link, root / "backup")
            self.assertEqual(version.read_bytes(), before)
            self.assertFalse(gl_link.exists())

    def test_rolls_back_all_code_and_gl_link_if_post_install_check_fails(self):
        files = BRIDGE.validate_archive(published_archive(), published_release())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "app"
            app.mkdir()
            (app / "INSTALLER-MARKER").write_text("global-home-nodes-v2\n", encoding="utf-8")
            (app / "VERSION.json").write_text('{"version":"2.0.1","adapter_version":"1.0.0"}\n', encoding="utf-8")
            (app / "update_manager.py").write_text("legacy updater\n", encoding="utf-8")
            gl_link = root / "usr" / "local" / "bin" / "gl"
            calls = []

            def fail_after_replace(path):
                calls.append(path)
                if len(calls) == 2:
                    raise BRIDGE.UpgradeError("post-install import check failed")

            with self.assertRaisesRegex(BRIDGE.UpgradeError, "rolled back"):
                BRIDGE.install_verified_files(
                    files, app, gl_link, root / "backup", smoke_test=fail_after_replace
                )
            self.assertEqual(json.loads((app / "VERSION.json").read_text())["version"], "2.0.1")
            self.assertEqual((app / "update_manager.py").read_text(), "legacy updater\n")
            self.assertFalse((app / "gl").exists())
            self.assertFalse((app / "relay_export.py").exists())
            self.assertFalse(gl_link.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

