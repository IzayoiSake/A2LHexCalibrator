"""Exercise widget callbacks without modifying user firmware or opening dialogs."""

import unittest
from unittest.mock import patch
from tkinter import ttk
from a2l_hex_calibrator.ui.editor import Editor
from a2l_hex_calibrator.ui.geometry import startup_bounds
from a2l_hex_calibrator.ui.keymap import validate_keys, DEFAULT_KEYS
from a2l_hex_calibrator import A2L, HexImage, Session
from tests.fixtures import description, firmware
import struct


class GuiTests(unittest.TestCase):
    def test_hex_overwrite_confirm_and_cancel(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            self.app.hex_path = Path(tmp) / "source.hex"
            self.app.hex_path.write_bytes(self.app.image.content)
            target = Path(tmp) / "output.hex"
            target.write_bytes(b"old output")
            with (
                patch("tkinter.messagebox.askokcancel", return_value=True),
                patch("tkinter.filedialog.asksaveasfilename", return_value=str(target)),
                patch("tkinter.messagebox.askyesno", return_value=False),
                patch.object(self.app, "run_job") as job,
            ):
                self.app.save()
                job.assert_not_called()
                self.assertEqual(target.read_bytes(), b"old output")
            with (
                patch("tkinter.messagebox.askokcancel", return_value=True),
                patch("tkinter.filedialog.asksaveasfilename", return_value=str(target)),
                patch("tkinter.messagebox.askyesno", return_value=True),
                patch.object(self.app, "run_job") as job,
            ):
                self.app.save()
                job.call_args.args[1]()
                self.assertEqual(target.read_bytes(), self.app.image.content)

    def test_windows_numlock_does_not_become_alt(self):
        from types import SimpleNamespace

        with patch("a2l_hex_calibrator.ui.shortcuts.os.name", "nt"):
            with patch.object(self.app, "run_shortcut") as run:
                for state in (0, 8, 10):
                    event = SimpleNamespace(
                        keysym="Return", keycode=13, state=state, widget=self.app.tree
                    )
                    self.assertEqual(self.app.dispatch_shortcut(event), "break")
                self.assertEqual(run.call_count, 3)
                run.assert_called_with("edit")
            with patch.object(self.app, "run_shortcut") as run:
                event = SimpleNamespace(keysym="s", keycode=83, state=12, widget=self.app.tree)
                self.app.dispatch_shortcut(event)
                run.assert_called_once_with("save_plan")
            confirm = unittest.mock.Mock()
            event = SimpleNamespace(keysym="Return", keycode=13, state=8, widget=self.app.tree)
            self.app.dispatch_shortcut(event, dialog=self.app, confirm=confirm)
            confirm.assert_called_once()

    def setUp(self):
        self.app = Editor()
        self.app.withdraw()
        self.app.a2l = A2L(description())
        self.app.image = HexImage(firmware(struct.pack("<f", 1.25)))
        self.app.session = Session(self.app.a2l, self.app.image)
        self.app.refresh()
        self.app.tree.selection_set("0")

    def tearDown(self):
        for callback in self.app.tk.call("after", "info"):
            self.app.after_cancel(callback)
        self.app.destroy()

    def test_bottom_buttons_visible_at_smaller_window(self):
        self.app.deiconify()
        self.app.minsize(1, 1)
        for width, height in ((1024, 700), (1440, 900), (2160, 1284)):
            self.app.geometry(f"{width}x{height}")
            self.app.update()
            for button in self.app.buttons:
                self.assertTrue(button.winfo_ismapped(), button.cget("text"))
                self.assertGreaterEqual(button.winfo_height(), button.winfo_reqheight())
                self.assertLessEqual(
                    button.winfo_rooty() + button.winfo_height(),
                    self.app.winfo_rooty() + self.app.winfo_height(),
                )

    def widgets(self, parent):
        for child in parent.winfo_children():
            yield child
            yield from self.widgets(child)

    def test_edit_confirm_undo_and_revert(self):
        self.app.edit()
        widgets = list(self.widgets(self.app))
        inputs = [
            w for w in widgets if isinstance(w, ttk.Combobox) and w.cget("state") != "readonly"
        ]
        inputs[-1].set("2.5")
        confirm = [
            w for w in widgets if isinstance(w, ttk.Button) and w.cget("text") == "确认修改"
        ][0]
        with patch("tkinter.messagebox.askokcancel", return_value=True):
            confirm.invoke()
        self.assertEqual(self.app.session.entries[0].raw(), 2.5)
        self.assertEqual(self.app.tree.set("0", "status"), "已修改")
        self.app.undo()
        self.assertEqual(self.app.session.entries[0].raw(), 1.25)
        self.app.session.set_value(self.app.session.entries[0], "3.5")
        self.app.refresh()
        self.app.revert()
        self.assertFalse(self.app.session.entries[0].changed)

    def test_search_and_changed_filter(self):
        self.app.query.set("*GAIN")
        self.app.refresh()
        self.assertEqual(len(self.app.tree.get_children()), 1)
        self.app.filter.set("已修改")
        self.app.refresh()
        self.assertEqual(len(self.app.tree.get_children()), 0)
        self.app.session.set_value(self.app.session.entries[0], "3")
        self.app.refresh()
        self.assertEqual(len(self.app.tree.get_children()), 1)

    def test_dialog_center_and_buttons_visible_after_parent_resize(self):
        import tkinter as tk

        self.app.deiconify()
        for ratio in (0.8, 1.0):
            width = round(self.app.winfo_screenwidth() * ratio * 0.75)
            height = round(self.app.winfo_screenheight() * ratio * 0.75)
            self.app.geometry(f"{width}x{height}+80+60")
            self.app.update()
            self.app.edit()
            self.app.update()
            dialog = next(w for w in self.app.winfo_children() if isinstance(w, tk.Toplevel))
            self.assertGreaterEqual(dialog.winfo_width(), round(width * 0.65))
            self.assertLess(
                abs(
                    dialog.winfo_x()
                    + dialog.winfo_width() / 2
                    - (self.app.winfo_rootx() + width / 2)
                ),
                3,
            )
            for button in (w for w in self.widgets(dialog) if isinstance(w, ttk.Button)):
                self.assertGreaterEqual(button.winfo_height(), button.winfo_reqheight())
                self.assertLessEqual(
                    button.winfo_rooty() + button.winfo_height(),
                    dialog.winfo_rooty() + dialog.winfo_height(),
                )
            dialog.destroy()

    def test_batch_edit_and_atomic_undo(self):
        self.app.a2l = A2L(description(kind="VAL_BLK", extra="MATRIX_DIM 2"))
        self.app.session = Session(self.app.a2l, HexImage(firmware(struct.pack("<ff", 1, 2))))
        self.app.refresh()
        self.app.select_all()
        self.app.edit()
        widgets = list(self.widgets(self.app))
        entry = [w for w in widgets if isinstance(w, ttk.Entry) and w is not self.app.search][-1]
        entry.insert(0, "3.5")
        button = next(
            w
            for w in widgets
            if isinstance(w, ttk.Button) and w.cget("text") == "校验并确认批量修改"
        )
        with patch("tkinter.messagebox.askokcancel", return_value=True):
            button.invoke()
        self.assertEqual([e.raw() for e in self.app.session.entries], [3.5, 3.5])
        self.assertEqual(len(self.app.tree.selection()), 2)
        self.app.undo()
        self.assertEqual([e.raw() for e in self.app.session.entries], [1, 2])

    def test_enter_confirms_edit(self):
        import tkinter as tk

        self.app.deiconify()
        self.app.edit()
        self.app.update()
        dialog = next(w for w in self.app.winfo_children() if isinstance(w, tk.Toplevel))
        entry = next(w for w in self.widgets(dialog) if isinstance(w, ttk.Combobox))
        entry.set("2.5")
        entry.focus_force()
        self.app.update()
        with patch("tkinter.messagebox.askokcancel", return_value=True):
            entry.event_generate("<Return>")
            self.app.update()
        self.assertEqual(self.app.session.entries[0].raw(), 2.5)

    def test_keyboard_only_repeat_and_control_shortcut(self):
        import tkinter as tk

        self.app.deiconify()
        self.app.update()
        for value in ("2.5", "3.5"):
            self.app.tree.focus_force()
            self.app.update()
            self.app.tree.event_generate("<Return>")
            self.app.update()
            dialog = next(w for w in self.app.winfo_children() if isinstance(w, tk.Toplevel))
            entry = next(w for w in self.widgets(dialog) if isinstance(w, ttk.Combobox))
            self.assertEqual(self.app.focus_get(), entry)
            entry.set(value)
            with patch("tkinter.messagebox.askokcancel", return_value=True):
                entry.event_generate("<Return>")
                self.app.update()
            self.assertEqual(self.app.session.entries[0].raw(), float(value))
            self.assertEqual(self.app.focus_get(), self.app.tree)
        with patch.object(self.app, "save_plan") as save:
            self.app.commands["save_plan"] = ("保存方案", save)
            self.app.search.focus_force()
            self.app.update()
            self.app.search.event_generate("<Control-s>")
            self.app.update()
            save.assert_called_once()

    def test_json_overwrite_confirm_and_cancel(self):
        import tempfile
        from pathlib import Path

        self.app.session.set_value(self.app.session.entries[0], "3")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text("old", encoding="utf-8")
            with (
                patch("tkinter.filedialog.asksaveasfilename", return_value=str(path)),
                patch("tkinter.messagebox.askyesno", return_value=False),
            ):
                self.app.save_plan()
            self.assertEqual(path.read_text(encoding="utf-8"), "old")
            with (
                patch("tkinter.filedialog.asksaveasfilename", return_value=str(path)),
                patch("tkinter.messagebox.askyesno", return_value=True),
            ):
                self.app.save_plan()
            self.assertEqual(path.read_text(encoding="utf-8"), self.app.session.export_changes())

    def test_settings_save_and_reload(self):
        import tempfile
        import tkinter as tk
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            self.app.settings_path = Path(directory) / "keys.json"
            self.app.shortcut_settings()
            self.app.update()
            dialog = next(w for w in self.app.winfo_children() if isinstance(w, tk.Toplevel))
            inputs = [w for w in self.widgets(dialog) if isinstance(w, ttk.Entry)]
            inputs[2].delete(0, "end")
            inputs[2].insert(0, "Ctrl+Alt+K")
            next(
                w
                for w in self.widgets(dialog)
                if isinstance(w, ttk.Button) and w.cget("text") == "保存"
            ).invoke()
            self.assertEqual(self.app.shortcuts["edit"], "Ctrl+Alt+K")
            import json

            self.assertEqual(
                json.loads(self.app.settings_path.read_text(encoding="utf-8"))["edit"], "Ctrl+Alt+K"
            )
            self.assertEqual(self.app.edit_menu.entrycget(2, "accelerator"), "Ctrl+Alt+K")

    def test_batch_validation_failure_changes_nothing(self):
        self.app.a2l = A2L(description(kind="VAL_BLK", extra="MATRIX_DIM 2"))
        session = Session(self.app.a2l, HexImage(firmware(struct.pack("<ff", 1, 2))))
        session.entries[1].error = "测试不可读取项"
        with self.assertRaises(ValueError):
            session.prepare_batch(session.entries, "3")
        self.assertTrue(all(e.pending is None for e in session.entries))


class WindowSizeTests(unittest.TestCase):
    def test_shortcut_conflicts_and_normalization(self):
        keys = dict(DEFAULT_KEYS)
        keys["edit"] = "ctrl+alt+k"
        self.assertEqual(validate_keys(keys)["edit"], "Ctrl+Alt+K")
        keys["undo"] = "Ctrl+Alt+K"
        with self.assertRaises(ValueError):
            validate_keys(keys)
        keys["undo"] = "x"
        with self.assertRaises(ValueError):
            validate_keys(keys)

    def test_work_area_excludes_bottom_taskbar(self):
        self.assertEqual(startup_bounds((0, 0, 1920, 1040)), (1440, 780, 240, 130))

    def test_taskbar_at_left(self):
        self.assertEqual(startup_bounds((80, 0, 1920, 1080)), (1380, 810, 310, 135))

    def test_secondary_monitor_negative_origin(self):
        self.assertEqual(startup_bounds((-1920, 0, 0, 1040)), (1440, 780, -1680, 130))


if __name__ == "__main__":
    unittest.main(verbosity=2)
