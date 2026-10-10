"""编辑会话聚合根；UI 不直接操作 HEX 字节或绕过参数校验。"""

from __future__ import annotations

from ..errors import FormatError
from ..formats.a2l import A2L
from ..formats.intel_hex import HexImage
from ..services.change_plan import ChangePlanCodec
from ..services.hex_writer import HexWriter
from .entry import Entry


class Session:
    """一次 A2L/HEX 配对的编辑会话；集中管理条目、修改校验和补丁。"""

    def __init__(self, a2l: A2L, image: HexImage | None = None):
        """按元素展开标定对象并读取原始字节；单项错误记录在条目中。"""
        self.a2l = a2l
        self.image = image
        self.entries = []
        for p in a2l.parameters:
            for i in range(p.count if not p.problem else 1):
                e = Entry(p, i, error=p.problem)
                if not e.error and image:
                    try:
                        e.original = image.read(e.address, p.size)
                        p.conversion.physical(e.raw())
                    except (ValueError, OverflowError, ZeroDivisionError) as exc:
                        e.error = str(exc)
                self.entries.append(e)

    def patch(self):
        """只收集实际变化的字节；同地址冲突必须报错。"""
        patch = {}
        for e in self.entries:
            if not e.changed:
                continue
            for i, (old, new) in enumerate(zip(e.original, e.pending)):
                if old != new:
                    address = e.address + i
                    if address in patch and patch[address] != new:
                        raise FormatError(f"参数地址重叠且修改冲突：0x{address:X}")
                    patch[address] = new
        return patch

    def set_value(self, entry: Entry, text: str, raw_mode=False):
        """先完整校验再设置 pending，不直接保存磁盘。"""
        entry.pending = self.validate_value(entry, text, raw_mode)

    def validate_value(self, entry: Entry, text: str, raw_mode=False):
        """除编码校验外还拒绝与其他标定对象重叠的修改。"""
        encoded = entry.encode(text, raw_mode)
        # Reject edits overlapping any other named calibration element. Conservative
        # handling prevents aliases/bitfields from silently changing another row.
        if encoded != entry.original:
            for other in self.entries:
                if other is entry or other.original is None:
                    continue
                if entry.address < other.address + len(
                    other.original
                ) and other.address < entry.address + len(encoded):
                    raise FormatError(f"地址与 {other.name} 重叠：为避免联动误改，禁止编辑")
        return encoded if encoded != entry.original else None

    def prepare_batch(self, entries, text, raw_mode=False):
        """整批预校验，任一项失败则不给调用方部分成功结果。"""
        changes = []
        errors = []
        for entry in entries:
            try:
                changes.append((entry, self.validate_value(entry, text, raw_mode)))
            except (ValueError, OverflowError) as exc:
                errors.append(f"{entry.name}: {exc}")
        if errors:
            raise FormatError("批量修改未应用，以下项目校验失败：\n" + "\n".join(errors))
        return changes

    def export_changes(self):
        """导出方案；实际格式规则交给 ChangePlanCodec。"""
        return ChangePlanCodec.export(self)

    def import_changes(self, text):
        """只验证方案，不应用；由调用者确认后统一更新 pending。"""
        return ChangePlanCodec.prepare_import(self, text)

    def save_new(self, path, source_path=None, overwrite=False):
        """委托安全写入服务；保存不会清除相对原 HEX 的修改状态。"""
        return HexWriter.save(self, path, source_path, overwrite)
