"""后端服务独立测试，不创建窗口或调用文件选择框。"""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from a2l_hex_calibrator.backend.services.files import FileService
from a2l_hex_calibrator.backend.services.editing import EditService
from tests.fixtures import description, session


class ServiceTests(unittest.TestCase):
    def test_loading_both_orders(self):
        with tempfile.TemporaryDirectory() as directory:
            a2l_path = Path(directory) / "test.a2l"
            hex_path = Path(directory) / "test.hex"
            a2l_path.write_text(description(), encoding="utf-8")
            hex_path.write_bytes(session().image.content)
            a2l, waiting = FileService.load_pair("a2l", a2l_path)
            self.assertIsNone(waiting.image)
            image, loaded = FileService.load_pair("hex", hex_path, a2l=a2l)
            self.assertEqual(loaded.entries[0].raw(), 1.25)
            _, waiting = FileService.load_pair("hex", hex_path)
            self.assertIsNone(waiting)
            _, loaded = FileService.load_pair("a2l", a2l_path, image=image)
            self.assertEqual(loaded.entries[0].raw(), 1.25)

    def test_plan_storage_and_prepare_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            source = session()
            source.set_value(source.entries[0], "2.5")
            FileService.save_plan(path, source)
            source.set_value(source.entries[0], "3.5")
            FileService.save_plan(path, source)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("address", str(data))
            target = session()
            changes = FileService.load_plan(path, target)
            self.assertFalse(target.entries[0].changed)
            history = []
            EditService.apply(changes, history)
            self.assertEqual(target.entries[0].raw(), 3.5)
            EditService.undo(history)
            self.assertEqual(target.entries[0].raw(), 1.25)

    def test_text_replace_failure_keeps_existing_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text("old", encoding="utf-8")
            with patch(
                "a2l_hex_calibrator.backend.services.files.os.replace", side_effect=PermissionError
            ):
                with self.assertRaises(PermissionError):
                    FileService.write_text_atomic(path, "new")
            self.assertEqual(path.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_revert_can_be_undone(self):
        model = session()
        history = []
        EditService.set_value(model, model.entries[0], "9", False, history)
        EditService.revert(model.entries, history)
        self.assertFalse(model.entries[0].changed)
        EditService.undo(history)
        self.assertEqual(model.entries[0].raw(), 9)

    def test_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sub" / "keys.json"
            FileService.write_settings(path, {"confirm": "Enter"})
            self.assertEqual(FileService.read_settings(path), {"confirm": "Enter"})
