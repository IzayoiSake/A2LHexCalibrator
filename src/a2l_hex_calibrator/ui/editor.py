"""主窗口组合入口；具体布局和操作按职责放在相邻模块。"""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import messagebox
from .constants import TITLE, VERSION
from .shortcuts import ShortcutMixin
from .layout import LayoutMixin
from .table import TableMixin
from .editing import EditingMixin
from .files import FileActionsMixin
from .jobs import JobMixin
from .language import LanguageMixin


class Editor(
    LanguageMixin,
    ShortcutMixin,
    LayoutMixin,
    TableMixin,
    EditingMixin,
    FileActionsMixin,
    JobMixin,
    tk.Tk,
):
    """应用主窗口与界面状态所有者；按职责混入界面行为。

    只有这里初始化公共状态。各 Mixin 不自行创建 Tk 根窗口或保存重复会话。
    domain/services 不依赖 GUI，可直接由测试或未来其他前端调用。
    """

    def __init__(self, settings_path=None):
        """初始化会话、历史、任务队列，再建立界面和快捷键。"""
        super().__init__()
        self.setup_language(settings_path)
        self.title(f"{TITLE}  {VERSION}")
        self.a2l_path = None
        self.hex_path = None
        self.a2l = None
        self.image = None
        self.session = None
        self.history = []
        self.busy = False
        self.jobs = queue.Queue()
        self.search_job = None
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.style_ui()
        self.make_widgets()
        self.setup_shortcuts(settings_path)
        self.title(f"{self.tr('constants.a2l_hex_calibrator_firmware_calibration')}  {VERSION}")
        self.set_startup_size()
        self.after(80, self.poll)

    def help(self):
        """展示能力边界及安全使用说明。"""
        messagebox.showinfo(
            self.tr("common.help"),
            self.tr("editor.1_load_a_matching_a2l_and_intel_hex_pair_2_search_by_su"),
            parent=self,
        )

    def close(self):
        """后台工作未结束时不关闭；关闭前检查未保存修改。"""
        if self.busy:
            messagebox.showinfo(
                self.tr("editor.busy"),
                self.tr("editor.please_wait_for_the_current_file_operation_to_finish"),
                parent=self,
            )
            return
        if self.changed() and not messagebox.askyesno(
            self.tr("editor.close"),
            self.tr("editor.unsaved_editing_state_will_be_lost_saved_files_are_unaf"),
            parent=self,
        ):
            return
        self.destroy()
