import hashlib
import json
import os
import re
import unittest
import zipfile
from pathlib import Path


ROOT = Path(os.environ.get("GLOBAL_RELEASE_ROOT", Path(__file__).resolve().parents[1]))
VERSION = "2.1.3"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ReleaseArtifactTests(unittest.TestCase):
    def test_external_sha256_manifest_matches_all_release_files(self):
        manifest = ROOT / f"global-home-nodes-v{VERSION}-artifacts.sha256"
        entries = {}
        for line in manifest.read_text(encoding="utf-8").splitlines():
            digest, name = line.split("  ", 1)
            entries[name] = digest
        self.assertEqual(
            set(entries),
            {
                f"global-home-nodes-install-v{VERSION}.sh",
                f"global-home-nodes-v{VERSION}.zip",
                "update/manifest.json",
            },
        )
        for name, digest in entries.items():
            self.assertEqual(sha256(ROOT / name), digest, name)

    def test_archive_includes_updater_and_installer_copies_it_safely(self):
        archive_path = ROOT / f"global-home-nodes-v{VERSION}.zip"
        with zipfile.ZipFile(archive_path) as archive:
            self.assertIsNone(archive.testzip())
            names = set(archive.namelist())
            self.assertIn("global-home-nodes/update_manager.py", names)
            source = archive.read("global-home-nodes/install.sh").decode("utf-8")
            self.assertIn("update_manager.py", source)
            match = re.search(r"^RUNTIME_FILES='([^']+)'$", source, re.M)
            self.assertIsNotNone(match)
            self.assertIn("update_manager.py", match.group(1).split())
            self.assertGreaterEqual(source.count("for file in $RUNTIME_FILES"), 3)
            self.assertGreaterEqual(
                source.count("import core,deploy,lazycat_adapter,update_manager,relay_export"),
                2,
            )
            updater = archive.read("global-home-nodes/update_manager.py")
            self.assertIn(b"def update(", updater)
            self.assertIn(b"def _archive_files(", updater)

    def test_update_manifest_points_to_the_verified_archive(self):
        manifest = json.loads((ROOT / "update" / "manifest.json").read_text(encoding="utf-8"))
        archive = ROOT / f"global-home-nodes-v{VERSION}.zip"
        self.assertEqual(manifest["version"], VERSION)
        self.assertEqual(manifest["archive_path"], archive.name)
        self.assertEqual(manifest["archive_sha256"], sha256(archive))


if __name__ == "__main__":
    unittest.main(verbosity=2)

