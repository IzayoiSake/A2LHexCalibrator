"""A2L 原始值与物理值换算；只允许可确定且不含歧义的逆变换。"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from ..errors import FormatError
from .values import number


@dataclass
class Conversion:
    """保存单位、系数、查表点及有效域；与具体 HEX 地址解耦。"""

    kind: str = "IDENTICAL"
    unit: str = ""
    coefficients: tuple = ()
    labels: dict = field(default_factory=dict)
    points: tuple = ()
    domain: tuple = (-math.inf, math.inf)

    def lookup(self, value, inverse=False):
        """查找或分段线性插值；逆向换算交换坐标，禁止超范围外推。"""
        pts = sorted((y, x) for x, y in self.points) if inverse else list(self.points)
        for x, y in pts:
            if value == x:
                return y
        if self.kind == "TAB_NOINTP":
            raise FormatError("数值不在离散换算表中")
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x0 < value < x1:
                return y0 + (value - x0) * (y1 - y0) / (x1 - x0)
        raise FormatError("数值超出换算表范围；不做外推")

    def physical(self, raw):
        """原始存储值转物理值；RAT_FUNC 仅接受物理有效域内的唯一解。"""
        if self.kind == "IDENTICAL":
            return raw
        if self.kind == "LINEAR":
            a, b = self.coefficients
            return a * raw + b
        if self.kind == "RAT_FUNC":
            # ASAP2 rational function is physical -> internal.
            a, b, c, d, e, f = self.coefficients
            aa, bb, cc = a - raw * d, b - raw * e, c - raw * f
            if aa == 0:
                if bb == 0:
                    raise FormatError("RAT_FUNC 无唯一逆变换")
                roots = [-cc / bb]
            else:
                disc = bb * bb - 4 * aa * cc
                if disc < 0:
                    raise FormatError("RAT_FUNC 无实数解")
                roots = [(-bb + math.sqrt(disc)) / (2 * aa), (-bb - math.sqrt(disc)) / (2 * aa)]
            valid = sorted(
                set(
                    x
                    for x in roots
                    if self.domain[0] <= x <= self.domain[1]
                    and d * x * x + e * x + f != 0
                    and math.isfinite(x)
                )
            )
            if len(valid) != 1:
                raise FormatError("RAT_FUNC 在物理范围内无唯一解，禁止猜测")
            return valid[0]
        if self.kind in ("TAB_INTP", "TAB_NOINTP"):
            return self.lookup(raw)
        if self.kind == "TAB_VERB":
            return self.labels.get(raw, f"{raw} (未定义枚举)")
        raise FormatError(f"不支持换算：{self.kind}")

    def internal(self, value: str):
        """用户物理值或枚举文字转原始值；最终存储范围由 Entry 校验。"""
        if self.kind == "TAB_VERB":
            matching = [k for k, v in self.labels.items() if v == value]
            if len(matching) == 1:
                return matching[0]
            if len(matching) > 1:
                raise FormatError("枚举文字对应多个原始值，请输入原始数值")
            raw = number(value)
            if raw not in self.labels:
                raise FormatError("不是已定义的枚举值")
            return raw
        x = number(value)
        if self.kind == "IDENTICAL":
            return x
        if self.kind == "LINEAR":
            a, b = self.coefficients
            return (x - b) / a
        if self.kind == "RAT_FUNC":
            a, b, c, d, e, f = self.coefficients
            den = d * x * x + e * x + f
            if den == 0:
                raise FormatError("RAT_FUNC 分母为零")
            return (a * x * x + b * x + c) / den
        if self.kind in ("TAB_INTP", "TAB_NOINTP"):
            return self.lookup(x, inverse=True)
        raise FormatError(f"不支持换算：{self.kind}")
