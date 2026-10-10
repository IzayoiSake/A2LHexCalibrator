"""国际化回归：资源完整性、状态保留、键盘操作和旧设置兼容。"""

import ast
import json
from pathlib import Path
import re
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from a2l_hex_calibrator.backend.services.translation import TranslationService
from a2l_hex_calibrator.ui.editor import Editor
from tests.fixtures import session


class ResourceTests(unittest.TestCase):
    def test_catalog_keys_and_placeholders_match(self):
        service = TranslationService()
        cn, en = service.catalogs.values()
        self.assertEqual(cn.keys(), en.keys())
        for key in cn:
            self.assertEqual(service.fields(cn[key]), service.fields(en[key]), key)
            self.assertTrue(en[key].strip(), key)
            if key != "language.zh_CN":
                self.assertFalse(re.search("[\u4e00-\u9fff]", en[key]), key)

    def test_ui_has_no_chinese_display_literals(self):
        folder = Path(__file__).resolve().parents[1] / "src/a2l_hex_calibrator/ui"
        for path in folder.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docs = {
                id(n.value)
                for n in ast.walk(tree)
                if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
            }
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and id(node) not in docs
                ):
                    self.assertFalse(
                        re.search("[\u4e00-\u9fff]", node.value), (path.name, node.lineno)
                    )

    def test_invalid_language_and_override_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "en_US.json"
            path.write_text(
                json.dumps({"language.menu": "Choose language", "files.load_p0": "Broken {other}"}),
                encoding="utf-8",
            )
            service = TranslationService("en_US", directory)
            self.assertEqual(service.text("language.menu"), "Choose language")
            self.assertEqual(service.text("files.load_p0", p0="HEX"), "Load HEX")
            service.set_language("not_a_language")
            self.assertEqual(service.language, "zh_CN")
            path.write_text("invalid json", encoding="utf-8")
            self.assertEqual(
                TranslationService("en_US", directory).text("language.menu"), "Language"
            )


class LanguageGuiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = Path(self.directory.name) / "settings.json"
        # 旧配置没有 language 字段，仍能读取并保留快捷键。
        self.settings.write_text(json.dumps({"edit": "Ctrl+Alt+K"}), encoding="utf-8")
        self.app = Editor(settings_path=self.settings)
        self.app.session = session()
        self.app.a2l = self.app.session.a2l
        self.app.image = self.app.session.image
        self.app.refresh()
        self.app.tree.selection_set("0")

    def tearDown(self):
        for callback in self.app.tk.call("after", "info"):
            self.app.after_cancel(callback)
        self.app.destroy()
        self.directory.cleanup()

    def test_switch_preserves_pending_filter_selection_and_shortcuts(self):
        self.app.session.set_value(self.app.selected(), "2.5")
        self.app.query.set("*Gain")
        self.app.filter_chooser.current(2)
        original_session = self.app.session
        for language in ("en_US", "zh_CN", "en_US"):
            self.app.switch_language(language)
            self.app.update()
            self.assertIs(self.app.session, original_session)
            self.assertEqual(self.app.selected().raw(), 2.5)
            self.assertEqual(self.app.query.get(), "*Gain")
            self.assertEqual(self.app.filter_chooser.current(), 2)
            self.assertEqual(self.app.shortcuts["edit"], "Ctrl+Alt+K")
        self.assertEqual(self.app.tree.set("0", "status"), "Modified")
        self.assertEqual(self.app.edit_menu.entrycget(0, "label"), "Load A2L")
        saved = json.loads(self.settings.read_text(encoding="utf-8"))
        self.assertEqual(saved["language"], "en_US")
        self.assertEqual(saved["edit"], "Ctrl+Alt+K")
        self.app.setup_language(self.settings)
        self.assertEqual(self.app.translator.language, "en_US")

    def test_english_enter_edit_and_confirm(self):
        self.app.switch_language("en_US")
        self.app.deiconify()
        self.app.update()
        self.app.tree.focus_force()
        self.app.update()
        self.app.tree.event_generate("<Return>")
        self.app.update()
        dialog = next(w for w in self.app.winfo_children() if isinstance(w, tk.Toplevel))
        self.assertEqual(dialog.title(), "Edit calibration value")
        box = dialog.winfo_children()[0]
        entry = next(w for w in box.winfo_children() if isinstance(w, ttk.Combobox))
        entry.set("3.5")
        with patch("tkinter.messagebox.askokcancel", return_value=True):
            entry.event_generate("<Return>")
            self.app.update()
        self.assertEqual(self.app.selected().raw(), 3.5)
        self.app.undo()
        self.assertEqual(self.app.selected().raw(), 1.25)

    def test_busy_switch_is_noop_and_save_failure_preserves_ui(self):
        self.app.busy = True
        self.app.switch_language("en_US")
        self.assertEqual(self.app.translator.language, "zh_CN")
        self.app.busy = False
        original_tree = self.app.tree
        with (
            patch(
                "a2l_hex_calibrator.ui.language.FileService.write_settings",
                side_effect=OSError("test"),
            ),
            patch("tkinter.messagebox.showerror"),
        ):
            self.app.switch_language("en_US")
        self.assertIs(self.app.tree, original_tree)
        self.assertEqual(self.app.translator.language, "zh_CN")

    def test_english_buttons_remain_visible(self):
        self.app.switch_language("en_US")
        self.app.deiconify()
        self.app.minsize(1, 1)
        self.app.geometry("1024x700")
        self.app.update()
        for button in self.app.buttons:
            self.assertGreaterEqual(button.winfo_height(), button.winfo_reqheight())
            self.assertLessEqual(
                button.winfo_rooty() + button.winfo_height(),
                self.app.winfo_rooty() + self.app.winfo_height(),
            )
