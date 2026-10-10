"""主窗口布局、屏幕工作区适配与弹窗居中。不在模块导入时创建窗口。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from .constants import TITLE
from .geometry import startup_bounds


class LayoutMixin:
    """主窗口布局、屏幕工作区适配与弹窗居中。仅由 Editor 混入使用，共享其控件与会话状态。"""

    def set_startup_size(self):
        """读取当前显示器工作区（不含任务栏），初始窗口占宽高的 75%。"""
        self.update_idletasks()
        area = (0, 0, self.winfo_screenwidth(), self.winfo_screenheight())
        border_w = border_h = 0
        try:
            import ctypes
            from ctypes import wintypes

            class MonitorInfo(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            user32 = ctypes.windll.user32
            user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            user32.GetAncestor.restype = wintypes.HWND
            user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
            user32.MonitorFromWindow.restype = wintypes.HANDLE
            user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
            user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            hwnd = user32.GetAncestor(self.winfo_id(), 2)  # GA_ROOT: Tk wrapper window
            monitor = user32.MonitorFromWindow(hwnd, 2)  # nearest monitor
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(info)
            if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                r = info.rcWork
                area = (r.left, r.top, r.right, r.bottom)
            outer, client = wintypes.RECT(), wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(outer)) and user32.GetClientRect(
                hwnd, ctypes.byref(client)
            ):
                border_w = (outer.right - outer.left) - (client.right - client.left)
                border_h = (outer.bottom - outer.top) - (client.bottom - client.top)
        except (AttributeError, OSError):
            pass
        width, height, x, y = startup_bounds(area)
        client_w, client_h = max(1, width - border_w), max(1, height - border_h)
        # A fixed minimum must not enlarge the initial window on smaller displays.
        self.minsize(round(client_w * 0.65), round(client_h * 0.65))
        self.geometry(f"{client_w}x{client_h}+{x}+{y}")

    def style_ui(self):
        """集中设置字体、主题和控件样式。"""
        self.configure(bg="#edf2f7")
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(".", font=("Microsoft YaHei UI", 10))
        st.configure("TFrame", background="#edf2f7")
        st.configure("TLabel", background="#edf2f7", foreground="#24354b")
        st.configure("Title.TLabel", font=("Microsoft YaHei UI", 19, "bold"))
        st.configure("TButton", padding=(12, 7))
        st.configure("Treeview", rowheight=28, background="white", fieldbackground="white")
        st.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"), padding=5)
        st.map("Treeview", background=[("selected", "#1e6091")], foreground=[("selected", "white")])

    def make_widgets(self):
        # Only the central pane absorbs extra space or shrinks. Toolbar rows
        # retain their content-derived height regardless of the text request.
        """创建控件与响应式网格，仅中央区域吸收空间变化，保留操作按钮。"""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        header = ttk.Frame(self, padding=(20, 16, 20, 8))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            header,
            text=self.tr("constants.a2l_hex_calibrator_firmware_calibration"),
            style="Title.TLabel",
        ).pack(side="left")
        ttk.Label(
            header, text=self.tr("layout.offline_editing_precise_byte_changes_source_protected")
        ).pack(side="right")
        paths = ttk.Frame(self, padding=(20, 4))
        paths.grid(row=1, column=0, sticky="ew")
        paths.columnconfigure(1, weight=1)
        self.buttons = []
        for row, name, command in [
            (0, self.tr("common.load_a2l"), lambda: self.load("a2l")),
            (1, self.tr("common.load_hex"), lambda: self.load("hex")),
        ]:
            b = ttk.Button(paths, text=name, command=command)
            b.grid(row=row, column=0, padx=(0, 12), pady=3)
            self.buttons.append(b)
        self.a2l_label = ttk.Label(paths, text=self.tr("layout.no_a2l_selected"))
        self.a2l_label.grid(row=0, column=1, sticky="w")
        self.hex_label = ttk.Label(paths, text=self.tr("layout.no_intel_hex_selected"))
        self.hex_label.grid(row=1, column=1, sticky="w")
        bar = ttk.Frame(self, padding=(20, 10))
        bar.grid(row=2, column=0, sticky="ew")
        for col, weight in enumerate((5, 45, 38, 12)):
            bar.columnconfigure(col, weight=weight, uniform="search")
        ttk.Label(bar, text=self.tr("common.search")).grid(row=0, column=0, sticky="w")
        self.query = tk.StringVar()
        self.search = ttk.Entry(bar, textvariable=self.query)
        self.search.grid(row=0, column=1, sticky="ew")
        self.query.trace_add("write", self.delayed_filter)
        search_hint = ttk.Label(
            bar, text=self.tr("layout.substring_search_any_characters_one_character")
        )
        search_hint.grid(row=0, column=2, sticky="ew")
        self.filter = tk.StringVar(value=self.tr("common.all"))
        chooser = ttk.Combobox(
            bar,
            values=[
                self.tr("common.all"),
                self.tr("editing.editable"),
                self.tr("editing.modified"),
                self.tr("common.not_editable"),
            ],
            textvariable=self.filter,
            state="readonly",
        )
        chooser.grid(row=0, column=3, sticky="ew")
        self.filter_chooser = chooser
        chooser.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        pane = ttk.Panedwindow(self, orient="vertical")
        pane.grid(row=3, column=0, sticky="nsew")
        table = ttk.Frame(pane)
        pane.add(table, weight=5)
        cols = ("name", "address", "type", "original", "current", "unit", "status")
        self.tree = ttk.Treeview(table, columns=cols, show="headings", selectmode="extended")
        for col, title in zip(
            cols,
            [
                self.tr("layout.calibration_name_linear_array_index"),
                self.tr("layout.address"),
                self.tr("layout.storage_type"),
                self.tr("layout.original_hex_physical"),
                self.tr("layout.current_physical"),
                self.tr("layout.unit"),
                self.tr("layout.status"),
            ],
        ):
            self.tree.heading(col, text=title, command=lambda c=col: self.sort(c))
            self.tree.column(col, minwidth=0, stretch=False)
        ys = tk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        xs = tk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)

        def resize_table(event):
            ys.configure(width=max(1, round(event.width * 0.014)))
            xs.configure(width=max(1, round(event.height * 0.035)))
            available = max(1, event.width - ys.winfo_reqwidth())
            ratios = (0.34, 0.11, 0.12, 0.15, 0.15, 0.05, 0.08)
            for col, ratio in zip(cols, ratios):
                self.tree.column(col, width=max(1, int(available * ratio)))

        table.bind("<Configure>", resize_table)
        self.tree.tag_configure("changed", background="#fff0c4", foreground="#724300")
        self.tree.tag_configure("unavailable", foreground="#8a929e")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.details())
        self.tree.bind("<Double-1>", lambda e: self.edit())
        details = ttk.Frame(pane, padding=(0, 8))
        pane.add(details, weight=1)
        self.detail = tk.Text(
            details,
            wrap="word",
            bg="#f7f9fc",
            fg="#26384f",
            relief="flat",
            font=("Microsoft YaHei UI", 10),
            padx=10,
            pady=8,
        )
        self.detail.pack(fill="both", expand=True)
        self.set_detail(self.tr("layout.load_a_matching_a2l_and_hex_pair_double_click_a_scalar_"))
        actions = ttk.Frame(self, padding=(20, 10))
        actions.grid(row=4, column=0, sticky="ew")
        for col, (title, cmd) in enumerate(
            [
                (self.tr("common.edit_batch_edit"), self.edit),
                (self.tr("common.revert_selected"), self.revert),
                (self.tr("common.undo"), self.undo),
                (self.tr("common.preview_changes"), self.preview),
                (self.tr("common.export_csv"), self.export),
                (self.tr("common.help"), self.help),
            ]
        ):
            b = ttk.Button(actions, text=title, command=cmd)
            actions.columnconfigure(col, weight=1, uniform="actions")
            b.grid(row=0, column=col, sticky="ew")
            self.buttons.append(b)
        b = ttk.Button(actions, text=self.tr("layout.save_as_hex"), command=self.save)
        actions.columnconfigure(6, weight=1, uniform="actions")
        b.grid(row=0, column=6, sticky="ew")
        self.buttons.append(b)
        plans = ttk.Frame(self)
        plans.grid(row=5, column=0, sticky="ew")
        for col, (title, command) in enumerate(
            [
                (self.tr("common.save_changes_json"), self.save_plan),
                (self.tr("common.load_changes_json"), self.load_plan),
            ]
        ):
            plans.columnconfigure(col, weight=1, uniform="plans")
            button = ttk.Button(plans, text=title, command=command)
            button.grid(row=0, column=col, sticky="ew")
            self.buttons.append(button)
        self.status = tk.StringVar(value=self.tr("layout.ready"))
        ttk.Label(self, textvariable=self.status, padding=(20, 8)).grid(
            row=6, column=0, sticky="ew"
        )

        def resize_layout(event):
            if event.widget is not self:
                return
            width, height = event.width, event.height
            for frame in (header, paths, bar, actions):
                frame.configure(padding=(round(width * 0.01), round(height * 0.006)))
            for label in (self.a2l_label, self.hex_label):
                label.configure(wraplength=round(width * 0.8))
            search_hint.configure(wraplength=round(width * 0.35))
            ttk.Style(self).configure("Treeview", rowheight=max(1, round(height * 0.028)))
            pane.grid_configure(padx=round(width * 0.01))

        self.bind("<Configure>", resize_layout, add="+")
        pane.bind("<Configure>", lambda event: pane.sashpos(0, round(event.height * 0.8)))

    def set_detail(self, text):
        """更新只读详情区域，避免用户误编辑展示文本。"""
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def center_dialog(self, win, width_ratio, height_ratio):
        """按主窗口比例定大小，结合内容最小需求居中弹出。"""
        self.update_idletasks()
        width = round(self.winfo_width() * width_ratio)
        height = round(self.winfo_height() * height_ratio)
        win.geometry(f"{width}x{height}")
        win.update_idletasks()
        # Content-derived minimum accommodates font scaling instead of fixed pixels.
        width = max(width, win.winfo_reqwidth())
        height = max(height, win.winfo_reqheight())
        x = self.winfo_rootx() + (self.winfo_width() - width) // 2
        y = self.winfo_rooty() + (self.winfo_height() - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.minsize(win.winfo_reqwidth(), win.winfo_reqheight())
        win.deiconify()
