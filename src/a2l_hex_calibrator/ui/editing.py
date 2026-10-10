"""单项/批量编辑、确认与撤销。不在模块导入时创建窗口。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from ..backend.domain.values import format_value
from ..backend.services.editing import EditService


class EditingMixin:
    """单项/批量编辑、确认与撤销。仅由 Editor 混入使用，共享其控件与会话状态。"""

    def edit(self):
        """编辑单项；多选时转批量界面，确认前展示实际存储值。"""
        if self.busy:
            return
        entries = self.selected_entries()
        if len(entries) > 1:
            self.edit_batch(entries)
            return
        e = self.selected()
        if not e:
            return
        if e.error or e.original is None or e.parameter.readonly:
            messagebox.showinfo(
                self.tr("editing.cannot_edit"),
                e.error
                or self.tr("editing.load_hex_first_a2l_read_only_parameters_cannot_be_edite"),
                parent=self,
            )
            return
        win = tk.Toplevel(self)
        win.title(self.tr("editing.edit_calibration_value"))
        win.withdraw()
        win.transient(self)
        win.grab_set()
        box = ttk.Frame(win)
        box.pack(fill="both", expand=True)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(4, weight=1)
        name_label = ttk.Label(box, text=e.name, font=("Microsoft YaHei UI", 11, "bold"))
        name_label.grid(row=0, column=0, sticky="ew")
        info_label = ttk.Label(
            box,
            text=self.tr(
                "editing.original_p0_current_p1_address_0x_p2_type_p3",
                p0=e.display(True),
                p1=e.display(),
                p2=format(e.address, "08X"),
                p3=e.parameter.dtype,
            ),
        )
        info_label.grid(row=1, column=0, sticky="ew")
        raw_mode = tk.BooleanVar(value=False)
        value = tk.StringVar(value=e.display())
        choices = list(e.parameter.conversion.labels.values())
        inp = ttk.Combobox(box, textvariable=value, values=choices)
        inp.grid(row=2, column=0, sticky="ew")

        def toggle():
            value.set(format_value(e.raw()) if raw_mode.get() else e.display())

        ttk.Checkbutton(
            box,
            text=self.tr("common.enter_raw_storage_value_otherwise_physical_value_enum_l"),
            variable=raw_mode,
            command=toggle,
        ).grid(row=3, column=0, sticky="w")
        hint = tk.StringVar(
            value=self.tr("editing.integers_accept_decimal_0x_hexadecimal_and_true_false_f")
        )
        hint_label = ttk.Label(box, textvariable=hint)
        hint_label.grid(row=4, column=0, sticky="new")

        def commit():
            try:
                encoded = e.encode(value.get(), raw_mode.get())
                actual = format_value(e.parameter.conversion.physical(e.raw(encoded)))
                if not messagebox.askokcancel(
                    self.tr("editing.confirm_stored_value"),
                    self.tr(
                        "editing.will_store_p0_bytes_p1_changes_stay_in_memory_until_you",
                        p0=actual,
                        p1=encoded.hex(" ").upper(),
                    ),
                    parent=win,
                ):
                    return
                EditService.set_value(self.session, e, value.get(), raw_mode.get(), self.history)
                win.destroy()
                self.refresh()
            except (ValueError, OverflowError) as exc:
                hint.set(str(exc))

        footer = ttk.Frame(box)
        footer.grid(row=5, column=0, sticky="ew")
        footer.columnconfigure(0, weight=2)
        footer.columnconfigure(1, weight=1, uniform="buttons")
        footer.columnconfigure(2, weight=1, uniform="buttons")
        ttk.Button(footer, text=self.tr("common.cancel"), command=win.destroy).grid(
            row=0, column=1, sticky="ew"
        )
        ttk.Button(footer, text=self.tr("editing.confirm_change"), command=commit).grid(
            row=0, column=2, sticky="ew"
        )

        def resize_dialog(event):
            if event.widget is not win:
                return
            box.configure(padding=(round(event.width * 0.03), round(event.height * 0.04)))
            for label in (name_label, info_label, hint_label):
                label.configure(wraplength=max(1, round(event.width * 0.92)))
            for child in box.winfo_children():
                child.grid_configure(pady=round(event.height * 0.015))

        win.bind("<Configure>", resize_dialog)
        self.center_dialog(win, 0.65, 0.65)
        self.install_edit_keys(win, commit, inp)
        inp.focus_set()
        inp.selection_range(0, "end")

    def edit_batch(self, entries):
        """所有选中项先校验再整体应用；一条历史记录支持整批撤销。"""
        win = tk.Toplevel(self)
        win.withdraw()
        win.title(self.tr("editing.batch_edit_p0_items", p0=len(entries)))
        win.transient(self)
        win.columnconfigure(0, weight=1)
        win.rowconfigure(1, weight=1)
        ttk.Label(
            win,
            text=self.tr(
                "editing.selected_p0_items_apply_one_value_only_after_all_items_", p0=len(entries)
            ),
        ).grid(row=0, column=0, sticky="ew")
        report = tk.Text(win, wrap="word")
        report.grid(row=1, column=0, sticky="nsew")
        scroll = tk.Scrollbar(win, command=report.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        report.configure(yscrollcommand=scroll.set)

        def show(text):
            report.configure(state="normal")
            report.delete("1.0", "end")
            report.insert("end", text)
            report.configure(state="disabled")

        show("\n".join(f"{e.name} [{e.parameter.conversion.unit}]：{e.display()}" for e in entries))
        value = tk.StringVar()
        inp = ttk.Entry(win, textvariable=value)
        inp.grid(row=2, column=0, columnspan=2, sticky="ew")
        raw = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            win,
            text=self.tr("common.enter_raw_storage_value_otherwise_physical_value_enum_l"),
            variable=raw,
        ).grid(row=3, column=0, sticky="w")

        def commit():
            try:
                changes = self.session.prepare_batch(entries, value.get(), raw.get())
                show(
                    "\n".join(
                        f"{e.name}：{e.display()} → "
                        f"{format_value(e.parameter.conversion.physical(e.raw(pending or e.original)))}"
                        for e, pending in changes
                    )
                )
                if not messagebox.askokcancel(
                    self.tr("editing.confirm_batch_edit"),
                    self.tr(
                        "editing.validated_p0_items_preview_updated_input_p1_apply_undo_",
                        p0=len(changes),
                        p1=value.get(),
                    ),
                    parent=win,
                ):
                    return
                EditService.apply(changes, self.history)
                win.destroy()
                self.refresh()
            except (ValueError, OverflowError) as exc:
                show(str(exc))

        footer = ttk.Frame(win)
        footer.grid(row=4, column=0, columnspan=2, sticky="ew")
        for col in range(2):
            footer.columnconfigure(col, weight=1, uniform="batch")
        ttk.Button(footer, text=self.tr("common.cancel"), command=win.destroy).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(footer, text=self.tr("editing.validate_and_apply_batch"), command=commit).grid(
            row=0, column=1, sticky="ew"
        )
        win.bind(
            "<Configure>",
            lambda event: (
                scroll.configure(width=max(1, round(event.width * 0.014)))
                if event.widget is win
                else None
            ),
        )
        self.center_dialog(win, 0.75, 0.75)
        self.install_edit_keys(win, commit, inp)
        win.grab_set()
        inp.focus_set()

    def revert(self):
        """恢复选中已修改项，并保存撤销所需的旧 pending。"""
        entries = [e for e in self.selected_entries() if e.changed]
        if not self.busy and entries:
            EditService.revert(entries, self.history)
            self.refresh()

    def undo(self):
        """撤销最近一次单项、批量或方案导入修改。"""
        if not self.busy and self.history:
            EditService.undo(self.history)
            self.refresh()

    def preview(self):
        """只读展示修改值与具体字节，供生成固件前核对。"""
        if self.busy or not self.session:
            return
        changes = [e for e in self.session.entries if e.changed]
        win = tk.Toplevel(self)
        win.title(self.tr("editing.pending_changes"))
        text = tk.Text(win, wrap="none", font=("Consolas", 11))
        scroll = ttk.Scrollbar(win, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.insert(
            "end",
            self.tr(
                "editing.changed_p0_items_p1_data_bytes",
                p0=len(changes),
                p1=len(self.session.patch()),
            ),
        )
        for e in changes:
            text.insert(
                "end",
                f"{e.name}  @0x{e.address:08X}\n  {e.display(True)} → {e.display()}\n"
                f'  {e.original.hex(" ").upper()} → {e.pending.hex(" ").upper()}\n\n',
            )
        text.configure(state="disabled")
        self.center_dialog(win, 0.8, 0.7)
