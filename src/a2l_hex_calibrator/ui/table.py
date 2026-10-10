"""表格筛选、排序、多选和详细信息。不在模块导入时创建窗口。"""

from __future__ import annotations

from ..backend.services.search import SearchQuery
from ..backend.domain.values import format_value


class TableMixin:
    """表格筛选、排序、多选和详细信息。仅由 Editor 混入使用，共享其控件与会话状态。"""

    def delayed_filter(self, *_):
        """输入防抖：取消旧任务后延迟刷新，避免每个按键立即重绘全表。"""
        if self.search_job:
            self.after_cancel(self.search_job)
        self.search_job = self.after(180, self.refresh)

    def entry_status(self, e):
        """把数据状态转换成界面状态文字，供筛选和编辑可用性判断。"""
        if e.error:
            return self.tr("table.unreadable")
        if e.original is None:
            return self.tr("table.waiting_for_hex")
        if e.parameter.readonly:
            return self.tr("table.a2l_read_only")
        if e.changed:
            return self.tr("editing.modified")
        return self.tr("editing.editable")

    def refresh(self):
        """按搜索和状态重建表格，同时恢复仍可见的选中项。"""
        self.search_job = None
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        if not self.session:
            self.status.set(
                self.tr("table.load_a2l_and_hex") if not self.busy else self.tr("table.loading")
            )
            return
        query = SearchQuery(self.query.get())
        count = 0
        readable = 0
        for i, e in enumerate(self.session.entries):
            status = self.entry_status(e)
            editable = e.original is not None and not e.error and not e.parameter.readonly
            readable += int(e.original is not None and not e.error)
            if not query.matches(e):
                continue
            if self.filter_chooser.current() == 2 and not e.changed:
                continue
            if self.filter_chooser.current() == 1 and not editable:
                continue
            if self.filter_chooser.current() == 3 and editable:
                continue
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    e.name,
                    f"0x{e.address:08X}",
                    e.parameter.dtype or e.parameter.kind,
                    e.display(True),
                    e.display(),
                    e.parameter.conversion.unit,
                    status,
                ),
                tags=("changed",) if e.changed else ("unavailable",) if not editable else (),
            )
            count += 1
        selected = [iid for iid in selected if self.tree.exists(iid)]
        if selected:
            self.tree.selection_set(selected)
            self.tree.see(selected[0])
        self.status.set(
            self.tr(
                "table.p0_calibration_objects_p1_expanded_items_p2_readable_p3",
                p0=len(self.a2l.parameters),
                p1=len(self.session.entries),
                p2=readable,
                p3=sum((e.changed for e in self.session.entries)),
                p4=count,
            )
        )
        self.details()

    def selected(self):
        """返回首个选中条目；无选择或无会话时返回 None。"""
        sel = self.tree.selection()
        return self.session.entries[int(sel[0])] if sel and self.session else None

    def select_all(self, event=None):
        """仅全选当前筛选结果，不包含被隐藏的参数。"""
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def selected_entries(self):
        """把控件行 ID 映射回会话条目，不依赖显示排序。"""
        return [self.session.entries[int(i)] for i in self.tree.selection()] if self.session else []

    def sort(self, col):
        """地址使用数值排序，其他列按忽略大小写的文本排序。"""
        items = list(self.tree.get_children())
        reverse = getattr(self, "last_sort", None) == col
        self.last_sort = None if reverse else col

        def key(i):
            e = self.session.entries[int(i)]
            if col == "address":
                return e.address
            return self.tree.set(i, col).casefold()

        for n, i in enumerate(sorted(items, key=key, reverse=reverse)):
            self.tree.move(i, "", n)

    def details(self):
        """展示元数据、原始/待写字节及不可编辑原因。"""
        e = self.selected()
        if not e:
            self.set_detail(
                self.tr("table.double_click_to_edit_arrays_use_zero_based_linear_memor")
            )
            return
        p = e.parameter
        text = self.tr(
            "table.p0_description_p1",
            p0=e.name,
            p1=p.description or self.tr("common.no_description_in_a2l"),
        )
        text += self.tr(
            "table.object_type_p0_dimensions_p1_byte_order_p2",
            p0=p.kind,
            p1=p.dimensions or self.tr("common.scalar"),
            p2=self.tr("common.little_endian") if p.endian == "<" else self.tr("common.big_endian"),
        )
        text += self.tr(
            "table.a2l_physical_range_p0_p1_not_hardware_safety_limits_con",
            p0=p.low,
            p1=p.high,
            p2=p.conversion.kind,
            p3=p.conversion.coefficients,
        )
        if e.error:
            text += self.tr("table.unreadable_p0", p0=e.error)
        elif e.original is not None:
            text += self.tr(
                "table.raw_value_p0_original_hex_bytes_p1",
                p0=format_value(e.raw()),
                p1=e.original.hex(" ").upper(),
            )
            text += self.tr("table.current_bytes_p0", p0=(e.pending or e.original).hex(" ").upper())
        else:
            text += self.tr("table.load_hex_to_read_actual_stored_values")
        if p.readonly:
            text += self.tr("table.a2l_declares_read_only_editing_is_disabled")
        self.set_detail(text)
