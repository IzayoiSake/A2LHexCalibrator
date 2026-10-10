"""数值输入和显示工具。纯函数无可变状态，保留为函数便于复用和测试。"""

from __future__ import annotations

import math
import re
from ..errors import FormatError


def number(value: str):
    """解析十进制、十六进制和布尔文本；拒绝 NaN/Inf，避免写入无效控制参数。"""
    value = value.strip()
    if value.lower() in ("true", "false"):
        return int(value.lower() == "true")
    if re.fullmatch(r"[+-]?0[xX][0-9a-fA-F]+", value):
        return int(value, 16)
    if re.fullmatch(r"[+-]?\d+", value):
        return int(value, 10)
    result = float(value)
    if not math.isfinite(result):
        raise FormatError("不允许写入 NaN 或无穷大")
    return result


def format_value(value):
    """保留 Python 浮点的可回读精度，不为显示美观而截断标定值。"""
    if isinstance(value, float):
        return repr(value)
    return str(value)
