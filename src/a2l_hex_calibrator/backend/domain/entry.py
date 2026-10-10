"""把标定对象展开成可编辑行；原始字节和待写字节严格分开。"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from ..errors import FormatError
from .parameter import Parameter, TYPES
from .values import number, format_value


@dataclass
class Entry:
    """单个标量/数组元素；pending 为 None 表示未修改，original 永远作为比较基准。"""

    parameter: Parameter
    index: int = 0
    original: bytes | None = None
    pending: bytes | None = None
    error: str = ""

    @property
    def name(self):
        """数组名称带线性下标，供 JSON 方案跨版本按名称匹配。"""
        return self.parameter.name + (f"[{self.index}]" if self.parameter.count > 1 else "")

    @property
    def address(self):
        """由对象起始地址和元素下标计算实际字节地址。"""
        return self.parameter.address + self.index * (
            self.parameter.size if self.parameter.dtype in TYPES else 0
        )

    @property
    def changed(self):
        """只有待写字节与原始字节不同才计入修改，避免无效补丁。"""
        return self.pending is not None and self.pending != self.original

    def raw(self, data=None):
        """按字节序和类型解码；存在位掩码时提取有效位。"""
        p = self.parameter
        data = (
            data
            if data is not None
            else self.pending if self.pending is not None else self.original
        )
        if data is None:
            raise FormatError(self.error or "HEX 未加载")
        value = struct.unpack(p.endian + TYPES[p.dtype], data)[0]
        if p.mask is not None:
            shift = (p.mask & -p.mask).bit_length() - 1
            value = (value & p.mask) >> shift
        return value

    def display(self, original=False):
        """显示物理值；未加载/不可读取的条目显示占位符而不是伪造零值。"""
        if self.error or self.original is None:
            return "—"
        return format_value(
            self.parameter.conversion.physical(self.raw(self.original if original else None))
        )

    def encode(self, text: str, raw_mode=False):
        """输入转实际存储字节，并校验只读、整数精度、位域和量化后的物理范围。"""
        p = self.parameter
        if self.error or self.original is None or p.problem or p.readonly:
            raise FormatError(self.error or p.problem or "只读参数")
        value = number(text) if raw_mode else p.conversion.internal(text.strip())
        if not math.isfinite(value):
            raise FormatError("不允许 NaN 或无穷大")
        fmt = TYPES[p.dtype]
        if fmt not in ("f", "d"):
            nearest = round(value)
            if value != nearest and abs(value - nearest) > 1e-9:
                raise FormatError("无法精确表示为整数；请检查缩放或输入原始整数")
            value = nearest
        if p.mask is not None:
            shift = (p.mask & -p.mask).bit_length() - 1
            if not 0 <= value <= p.mask >> shift:
                raise FormatError("数值超出位掩码范围")
            old = struct.unpack(p.endian + fmt, self.original)[0]
            stored = (old & ~p.mask) | (value << shift)
        else:
            stored = value
        try:
            encoded = struct.pack(p.endian + fmt, stored)
        except (OverflowError, struct.error) as exc:
            raise FormatError(f"数值超出 {p.dtype} 的存储范围") from exc
        actual = self.raw(encoded)
        if not math.isfinite(actual):
            raise FormatError("存储后不是有限数")
        phys = p.conversion.physical(actual)
        if p.conversion.kind == "TAB_VERB":
            if actual not in p.conversion.labels:
                raise FormatError("未定义的枚举值")
        else:
            if not p.low <= phys <= p.high:
                raise FormatError(f"存储后物理值 {phys} 超出 A2L 范围 [{p.low}, {p.high}]")
        return encoded
