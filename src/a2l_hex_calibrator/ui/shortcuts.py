"""快捷键绑定、优先级分发及配置界面。不在模块导入时创建窗口。"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox
from ..backend.services.files import FileService
from .keymap import DEFAULT_KEYS, normalize_key, validate_keys


class ShortcutMixin:
    """快捷键绑定、优先级分发及配置界面。仅由 Editor 混入使用，共享其控件与会话状态。"""

    def setup_shortcuts(self, settings_path):
        """建立命令表、菜单与配置；配置损坏时恢复默认键位并提示。"""
        self.settings_path = FileService.settings_path(settings_path)
        self.commands = {
            "load_a2l": (self.tr("common.load_a2l"), lambda: self.load("a2l")),
            "load_hex": (self.tr("common.load_hex"), lambda: self.load("hex")),
            "edit": (self.tr("common.edit_batch_edit"), self.edit),
            "revert": (self.tr("common.revert_selected"), self.revert),
            "undo": (self.tr("common.undo"), self.undo),
            "preview": (self.tr("common.preview_changes"), self.preview),
            "export": (self.tr("common.export_csv"), self.export),
            "help": (self.tr("common.help"), self.help),
            "save": (self.tr("shortcuts.save_as_hex"), self.save),
            "save_plan": (self.tr("common.save_changes_json"), self.save_plan),
            "load_plan": (self.tr("common.load_changes_json"), self.load_plan),
            "search": (self.tr("common.search"), lambda: self.search.focus_set()),
            "select_all": (self.tr("shortcuts.select_all_rows"), self.select_all),
            "confirm": (self.tr("shortcuts.confirm_dialog"), lambda: None),
            "cancel": (self.tr("shortcuts.cancel_dialog"), lambda: None),
        }
        self.shortcuts = dict(DEFAULT_KEYS)
        try:
            if FileService.exists(self.settings_path):
                self.shortcuts = validate_keys(
                    FileService.read_settings(self.settings_path), self.tr
                )
        except (ValueError, OSError, TypeError, AttributeError) as exc:
            self.status.set(self.tr("shortcuts.could_not_read_shortcuts_using_defaults_p0", p0=exc))
        self.menubar = tk.Menu(self)
        self.edit_menu = tk.Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(label=self.tr("shortcuts.edit"), menu=self.edit_menu)
        settings = tk.Menu(self.menubar, tearoff=False)
        settings.add_command(label=self.tr("shortcuts.shortcuts"), command=self.shortcut_settings)
        self.menubar.add_cascade(label=self.tr("shortcuts.settings"), menu=settings)
        self.configure(menu=self.menubar)
        self.add_language_menu()
        self.refresh_shortcut_menu()
        self.install_shortcut_scope(self, self.dispatch_shortcut)

    def install_shortcut_scope(self, window, callback):
        # Handle application commands before Tk widget class bindings consume
        # Ctrl keys (Entry/Text/Combobox), while unhandled typing stays native.
        """将应用按键处理放在 Tk 控件默认绑定之前，避免回车/Ctrl 被吞掉。"""
        tag = f"EditorKeys:{window}"
        self.bind_class(tag, "<KeyPress>", callback)

        def attach(widget):
            widget.bindtags((tag,) + tuple(t for t in widget.bindtags() if t != tag))
            for child in widget.winfo_children():
                if not isinstance(child, tk.Toplevel):
                    attach(child)

        attach(window)

        def cleanup(event):
            if event.widget is window:
                self.unbind_class(tag, "<KeyPress>")

        window.bind("<Destroy>", cleanup, add="+")

    def install_edit_keys(self, win, commit, inp):
        """弹窗注册确认/取消键；关闭后把焦点交回表格。"""
        self.install_shortcut_scope(win, lambda event: self.dispatch_shortcut(event, win, commit))

        def restore(event):
            if event.widget is win:
                self.after_idle(self.tree.focus_set)

        win.bind("<Destroy>", restore, add="+")
        win.after_idle(inp.focus_force)

    def refresh_shortcut_menu(self):
        """重建编辑菜单，并展示用户当前配置的快捷键。"""
        self.edit_menu.delete(0, "end")
        for name, (label, command) in self.commands.items():
            self.edit_menu.add_command(
                label=label,
                accelerator=self.shortcuts[name],
                command=lambda n=name: self.run_shortcut(n),
                state="disabled" if name in ("confirm", "cancel") else "normal",
            )

    def run_shortcut(self, name):
        """只在未执行后台任务、未打开模态窗口时执行主窗口命令。"""
        if not self.busy and self.grab_current() is None:
            self.commands[name][1]()

    def dispatch_shortcut(self, event, dialog=None, confirm=None):
        """按窗口上下文分发快捷键；Windows NumLock 不应被误判为 Alt。"""
        symbol = event.keysym
        if symbol == "KP_Enter":
            symbol = "Return"
        if os.name == "nt" and event.state & 4 and 65 <= event.keycode <= 90:
            symbol = chr(event.keycode)
        # Windows Tk uses Mod1 (0x8) for NumLock, NOT Alt. Treating it as
        # Alt makes every key fail while the numeric keypad is enabled.
        alt_mask = 0x20000 if os.name == "nt" else 0x8
        try:
            key = normalize_key(
                "+".join(
                    [
                        label
                        for mask, label in ((4, "Ctrl"), (alt_mask, "Alt"), (1, "Shift"))
                        if event.state & mask
                    ]
                    + [symbol]
                )
            )
        except ValueError:
            return
        name = next((name for name, assigned in self.shortcuts.items() if assigned == key), None)
        if dialog is not None:
            if name == "confirm" or key == "Enter":
                confirm()
                return "break"
            if name == "cancel" or key == "Esc":
                dialog.destroy()
                return "break"
            return
        if event.widget is self.tree and key == "Enter":
            self.run_shortcut("edit")
            return "break"
        if name is None or name in ("confirm", "cancel"):
            return
        # Preserve native entry/text editing shortcuts; table selection is scoped.
        if isinstance(event.widget, (ttk.Entry, ttk.Combobox, tk.Text)) and key in (
            "Ctrl+A",
            "Ctrl+Z",
        ):
            return
        self.run_shortcut(name)
        return "break"

    def shortcut_settings(self):
        """编辑、校验并持久化快捷键，成功后立即刷新菜单。"""
        win = tk.Toplevel(self)
        win.withdraw()
        win.title(self.tr("shortcuts.keyboard_shortcuts"))
        win.transient(self)
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)
        body = ttk.Frame(win)
        body.grid(row=0, column=0, sticky="nsew")
        variables = {}
        for col in range(4):
            body.columnconfigure(col, weight=1, uniform="keys")
        for index, (name, (label, _)) in enumerate(self.commands.items()):
            row, pair = divmod(index, 2)
            body.rowconfigure(row, weight=1)
            ttk.Label(body, text=label).grid(row=row, column=pair * 2, sticky="ew")
            variables[name] = tk.StringVar(value=self.shortcuts[name])
            ttk.Entry(body, textvariable=variables[name]).grid(
                row=row, column=pair * 2 + 1, sticky="ew"
            )
        ttk.Label(
            win,
            text=self.tr("shortcuts.examples_ctrl_shift_s_f2_enter_esc_leave_blank_to_disab"),
        ).grid(row=1, column=0, sticky="ew")
        footer = ttk.Frame(win)
        footer.grid(row=2, column=0, sticky="ew")

        def save():
            """确认设备校验责任和覆盖意图后，将 HEX 写入交给后台服务。"""
            try:
                mapping = validate_keys(
                    {name: var.get() for name, var in variables.items()}, self.tr
                )
                FileService.write_settings(
                    self.settings_path, {**mapping, "language": self.translator.language}
                )
                self.shortcuts = mapping
                self.refresh_shortcut_menu()
                win.destroy()
            except (ValueError, OSError) as exc:
                messagebox.showerror(self.tr("shortcuts.shortcuts_not_saved"), str(exc), parent=win)

        def reset():
            for name, var in variables.items():
                var.set(DEFAULT_KEYS[name])

        for col, (label, command) in enumerate(
            [
                (self.tr("shortcuts.restore_defaults"), reset),
                (self.tr("common.cancel"), win.destroy),
                (self.tr("shortcuts.save"), save),
            ]
        ):
            footer.columnconfigure(col, weight=1, uniform="settings")
            ttk.Button(footer, text=label, command=command).grid(row=0, column=col, sticky="ew")
        self.install_shortcut_scope(win, lambda event: self.dispatch_shortcut(event, win, save))
        self.center_dialog(win, 0.85, 0.8)
        win.grab_set()
