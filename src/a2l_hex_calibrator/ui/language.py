"""界面语言切换：只重建控件，不重建标定会话或清除撤销记录。"""

import tkinter as tk
from tkinter import messagebox

from ..backend.services.files import FileService
from ..backend.services.translation import TranslationService
from .constants import VERSION


class LanguageMixin:
    """语言偏好与界面更新协调器；配置文件操作全部交给服务层。"""

    def setup_language(self, settings_path):
        self.settings_path = FileService.settings_path(settings_path)
        language = "zh_CN"
        try:
            settings = FileService.read_settings(self.settings_path)
            language = settings.get("language", language)
        except (OSError, ValueError, AttributeError, TypeError):
            pass
        self.translator = TranslationService(language)

    def tr(self, key, **values):
        return self.translator.text(key, **values)

    def add_language_menu(self):
        self.language_var = tk.StringVar(value=self.translator.language)
        self.language_menu = tk.Menu(self.menubar, tearoff=False)
        for code in TranslationService.LANGUAGES:
            self.language_menu.add_radiobutton(
                label=self.tr("language." + code),
                value=code,
                variable=self.language_var,
                command=lambda code=code: self.switch_language(code),
            )
        self.menubar.add_cascade(label=self.tr("language.menu"), menu=self.language_menu)

    def switch_language(self, language):
        """保存偏好成功后立即切换；操作中或弹窗打开时保持原状态。"""
        if language not in TranslationService.LANGUAGES:
            return
        if self.busy or any(isinstance(child, tk.Toplevel) for child in self.winfo_children()):
            self.language_var.set(self.translator.language)
            return
        if language == self.translator.language:
            return
        try:
            FileService.write_settings(self.settings_path, {**self.shortcuts, "language": language})
        except (OSError, ValueError) as exc:
            self.language_var.set(self.translator.language)
            messagebox.showerror(self.tr("language.save_failed"), str(exc), parent=self)
            return

        # 保存纯界面状态；Session、pending 和 history 从始至终保留原对象。
        query = self.query.get()
        filter_index = self.filter_chooser.current()
        selected = self.tree.selection()
        focused = self.tree.focus()
        scroll = self.tree.yview()
        search_focused = self.focus_get() is self.search
        if self.search_job:
            self.after_cancel(self.search_job)
            self.search_job = None
        self.unbind("<Configure>")
        for child in self.winfo_children():
            child.destroy()
        self.translator.set_language(language)
        self.make_widgets()
        self.setup_shortcuts(self.settings_path)
        self.title(f"{self.tr('constants.a2l_hex_calibrator_firmware_calibration')}  {VERSION}")
        if self.a2l_path:
            self.a2l_label.configure(text=str(self.a2l_path))
        if self.hex_path:
            self.hex_label.configure(text=str(self.hex_path))
        self.query.set(query)
        self.filter_chooser.current(max(0, filter_index))
        if self.search_job:
            self.after_cancel(self.search_job)
            self.search_job = None
        self.refresh()
        self.tree.selection_set([item for item in selected if self.tree.exists(item)])
        if self.tree.exists(focused):
            self.tree.focus(focused)
        if scroll:
            self.tree.yview_moveto(scroll[0])
        self.details()
        (self.search if search_focused else self.tree).focus_set()
