"""文件选择、加载、HEX 保存和 JSON 方案操作。不在模块导入时创建窗口。"""

from __future__ import annotations

from tkinter import filedialog, messagebox
from ..backend.services.files import FileService
from ..backend.services.editing import EditService


class FileActionsMixin:
    """文件选择、加载、HEX 保存和 JSON 方案操作。仅由 Editor 混入使用，共享其控件与会话状态。"""

    def changed(self):
        """判断当前会话是否存在尚保留在内存中的修改。"""
        return self.session and any(e.changed for e in self.session.entries)

    def discard_ok(self):
        """重新加载前询问是否丢弃编辑状态。"""
        return not self.changed() or messagebox.askyesno(
            self.tr("files.unsaved_changes"),
            self.tr("files.reloading_discards_unsaved_edits_continue"),
            parent=self,
        )

    def load(self, kind, path=None):
        """后台解析文件；完成后在 Tk 主线程替换会话并刷新控件。"""
        if self.busy:
            return
        if path is None:
            path = filedialog.askopenfilename(
                parent=self,
                title=self.tr("files.load_p0", p0=kind.upper()),
                filetypes=[(kind.upper(), f"*.{kind}"), (self.tr("files.all_files"), "*.*")],
            )
        if not path or not self.discard_ok():
            return

        def work():
            return FileService.load_pair(kind, path, self.a2l, self.image)

        def done(result):
            data, session = result
            if kind == "a2l":
                self.a2l, self.a2l_path = data, FileService.path(path)
                self.a2l_label.configure(text=str(path))
            else:
                self.image, self.hex_path = data, FileService.path(path)
                self.hex_label.configure(text=str(path))
            self.session, self.history = session, []
            self.refresh()

        self.run_job(self.tr("files.parsing_p0", p0=kind.upper()), work, done)

    def export(self):
        """导出当前筛选列表为 CSV，并转义可能被表格软件当作公式的文本。"""
        if self.busy or not self.session:
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            initialfile="calibrations.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            rows = []
            for iid in self.tree.get_children():
                entry = self.session.entries[int(iid)]
                rows.append(
                    list(self.tree.item(iid, "values"))
                    + [entry.error or entry.parameter.description]
                )
            FileService.export_csv(path, rows)
            self.status.set(self.tr("files.exported_filtered_rows_p0", p0=path))
        except Exception as exc:
            messagebox.showerror(self.tr("files.export_failed"), str(exc), parent=self)

    def save_plan(self):
        """保存按名称索引的 JSON；允许确认覆盖，临时文件读回后才替换。"""
        if self.busy or not self.session:
            return
        if not self.changed():
            messagebox.showinfo(
                self.tr("files.no_changes"),
                self.tr("files.there_are_no_modified_parameters"),
                parent=self,
            )
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".json",
            initialfile="calibration_changes.json",
            filetypes=[(self.tr("common.changes_json"), "*.json")],
            confirmoverwrite=False,
        )
        if not path:
            return
        if FileService.exists(path) and not messagebox.askyesno(
            self.tr("files.overwrite_changes_file"),
            self.tr("files.file_already_exists_p0_overwrite", p0=path),
            parent=self,
        ):
            return
        try:
            FileService.save_plan(path, self.session)
            self.status.set(self.tr("files.saved_changes_by_name_without_addresses_p0", p0=path))
        except Exception as exc:
            messagebox.showerror(
                self.tr("files.could_not_save_changes_file"), str(exc), parent=self
            )

    def load_plan(self):
        """方案全部校验通过且用户确认后，一次性应用并记录撤销历史。"""
        if self.busy:
            return
        if not self.session or not self.image:
            messagebox.showinfo(
                self.tr("files.load_files_first"),
                self.tr("files.load_the_current_a2l_and_hex_before_importing_changes"),
                parent=self,
            )
            return
        path = filedialog.askopenfilename(
            parent=self, filetypes=[(self.tr("common.changes_json"), "*.json")]
        )
        if not path:
            return
        try:
            changes = FileService.load_plan(path, self.session)
            if not messagebox.askokcancel(
                self.tr("files.load_changes"),
                self.tr(
                    "files.matched_and_validated_p0_items_by_name_their_current_ed", p0=len(changes)
                ),
                parent=self,
            ):
                return
            changed_count = EditService.apply(changes, self.history)
            self.refresh()
            self.status.set(
                self.tr(
                    "files.loaded_p0_items_p1_actually_changed_preview_then_save_a",
                    p0=len(changes),
                    p1=changed_count,
                )
            )
        except Exception as exc:
            messagebox.showerror(
                self.tr("files.could_not_load_changes_nothing_applied"), str(exc), parent=self
            )

    def save(self):
        """确认设备校验责任和覆盖意图后，将 HEX 写入交给后台服务。"""
        if self.busy or not self.session or not self.image:
            return
        changes = sum(e.changed for e in self.session.entries)
        if not messagebox.askokcancel(
            self.tr("files.confirm_before_saving"),
            self.tr("files.pending_changes_p0_items_only_affected_parameter_bytes_", p0=changes),
            parent=self,
        ):
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".hex",
            initialdir=self.hex_path.parent,
            initialfile=self.hex_path.stem + "_modified.hex",
            filetypes=[("Intel HEX", "*.hex")],
            confirmoverwrite=False,
        )
        if not path:
            return
        overwrite = FileService.exists(path)
        if overwrite and not messagebox.askyesno(
            self.tr("files.overwrite_hex_file"),
            self.tr("files.file_already_exists_p0_overwrite", p0=path),
            parent=self,
        ):
            return

        def done(result):
            self.status.set(self.tr("files.saved_and_verified_p0", p0=path))
            messagebox.showinfo(
                self.tr("files.saved_successfully"),
                self.tr(
                    "files.p0_changed_parameters_p1_changed_data_bytes_p2_changed_",
                    p0=path,
                    p1=result["changed_parameters"],
                    p2=result["changed_bytes"],
                    p3=result["changed_records"],
                    p4=result["sha256"],
                ),
                parent=self,
            )

        self.run_job(
            self.tr("files.generating_hex_checking_byte_differences_and_verifying_"),
            lambda: self.session.save_new(path, self.hex_path, overwrite=overwrite),
            done,
        )
