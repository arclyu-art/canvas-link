import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("release_build",ROOT/"release.py")
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_explicit_allowlist_excludes_unknown_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in release.FILES:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text("synthetic source")
            (root/"src/canvaslink").mkdir(parents=True);(root/"src/canvaslink/__init__.py").write_text("")
            (root/"tests").mkdir();(root/"private-cookies.json").write_text("DO_NOT_SHIP")
            selected=release.source_files(root)
            self.assertNotIn(root/"private-cookies.json",selected)
    def test_state_and_machine_path_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/"session.dpapi";path.write_bytes(b"encrypted")
            with self.assertRaises(ValueError):release.audit_file(path)
            path=root/"source.py";path.write_text(str(Path.home()),encoding="utf-8")
            with self.assertRaises(ValueError):release.audit_file(path)


if __name__=="__main__":unittest.main()
