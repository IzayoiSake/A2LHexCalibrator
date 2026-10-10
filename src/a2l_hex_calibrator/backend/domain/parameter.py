"""标定对象定义：描述元数据，不保存界面状态或文件句柄。"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from .conversion import Conversion

TYPES = {
    "UBYTE": "B",
    "SBYTE": "b",
    "UWORD": "H",
    "SWORD": "h",
    "ULONG": "I",
    "SLONG": "i",
    "A_UINT64": "Q",
    "A_INT64": "q",
    "FLOAT32_IEEE": "f",
    "FLOAT64_IEEE": "d",
}


@dataclass
class Parameter:
    """A2L 中的单个标定对象，包含类型、维度、字节序、地址和物理范围。"""

    name: str
    description: str = ""
    address: int = 0
    dtype: str = ""
    endian: str = "<"
    count: int = 1
    dimensions: tuple = ()
    low: float = -math.inf
    high: float = math.inf
    conversion: Conversion = field(default_factory=Conversion)
    mask: int | None = None
    readonly: bool = False
    problem: str = ""
    kind: str = ""

    @property
    def size(self):
        """一个数组元素的字节数，不是整个数组的总长度。"""
        return struct.calcsize(TYPES[self.dtype])
