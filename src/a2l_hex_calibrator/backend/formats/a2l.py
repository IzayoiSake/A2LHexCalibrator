"""A2L 语义解析：将存储布局、换算定义映射为 Parameter 对象。
不支持的布局保留为不可编辑条目，不能猜测地址。"""

from __future__ import annotations

import math
import re
from pathlib import Path
from ..errors import FormatError
from ..domain.parameter import Parameter, TYPES
from ..domain.conversion import Conversion
from ..domain.values import number
from .a2l_syntax import Block, A2LBlockParser, unquote, opt


class A2L:
    """单 MODULE 的解析结果；parameters 包含可支持对象及明确的问题原因。"""

    def __init__(self, text: str):
        """先索引布局/换算表，再逐项验证地址、字节序、维度和换算范围。"""
        if re.search(r"(?m)^\s*/include\b", text):
            raise FormatError("A2L 含 /include，请先合并外部定义后加载")
        root = A2LBlockParser.parse(text)

        def walk(b):
            yield b
            for child in b.children:
                yield from walk(child)

        modules = [b for b in walk(root) if b.kind == "MODULE"]
        if len(modules) != 1:
            raise FormatError("需要恰好一个 MODULE 的 A2L；多模块文件请先导出目标模块")
        module = modules[0]
        self.module = unquote(module.tokens[0]) if module.tokens else ""
        groups = {}
        for b in module.children:
            groups.setdefault(b.kind, []).append(b)

        def named(kind):
            out = {}
            for b in groups.get(kind, []):
                if not b.tokens or b.tokens[0] in out:
                    raise FormatError(f"{kind} 名称缺失或重复")
                out[b.tokens[0]] = b
            return out

        layouts = named("RECORD_LAYOUT")
        methods = named("COMPU_METHOD")
        tables = named("COMPU_VTAB")
        numeric_tables = named("COMPU_TAB")
        commons = groups.get("MOD_COMMON", [])
        default_order = opt(commons[0].tokens, "BYTE_ORDER") if len(commons) == 1 else None
        self.parameters = []
        # AXIS_PTS describes separately stored calibration axes. Only direct layouts
        # with explicit maximum length and no runtime count prefix are supported.
        axis_blocks = []
        for axis in groups.get("AXIS_PTS", []):
            t = axis.tokens
            if len(t) < 10:
                raise FormatError("AXIS_PTS 定义不完整")
            axis_blocks.append(
                Block(
                    "AXIS_PTS",
                    [t[0], t[1], "VAL_BLK", t[2], t[4], t[5], t[6], t[8], t[9], "NUMBER", t[7]]
                    + t[10:],
                    axis.children,
                )
            )
        for b in groups.get("CHARACTERISTIC", []) + axis_blocks:
            t = b.tokens
            if not t:
                raise FormatError("CHARACTERISTIC 名称为空")
            p = Parameter(t[0])
            self.parameters.append(p)
            try:
                if len(t) < 9:
                    raise FormatError("CHARACTERISTIC 定义不完整")
                p.description, p.kind = unquote(t[1]), t[2]
                p.address, layout_name = int(t[3], 0), t[4]
                p.low, p.high = number(t[7]), number(t[8])
                if p.address < 0 or p.low > p.high:
                    raise FormatError("地址或范围无效")
                p.readonly = "READ_ONLY" in t[9:]
                if p.kind not in ("VALUE", "VAL_BLK", "CURVE", "MAP", "CUBOID", "CUBE_4", "CUBE_5"):
                    raise FormatError(f"暂不支持 {p.kind} 存储，禁止猜测地址布局")
                if any(x in t[9:] for x in ["SYMBOL_LINK", "ECU_ADDRESS_EXTENSION"]):
                    extension = opt(t[9:], "ECU_ADDRESS_EXTENSION", default="0")
                    if int(extension, 0) != 0:
                        raise FormatError("非零 ECU_ADDRESS_EXTENSION 不可直接映射 HEX")
                if any(
                    x in t[9:]
                    for x in ["ADDRESS_TYPE", "VIRTUAL_CHARACTERISTIC", "DEPENDENT_CHARACTERISTIC"]
                ):
                    raise FormatError("间接或虚拟标定对象不支持直接编辑")
                if any(
                    c.kind in ("VIRTUAL_CHARACTERISTIC", "DEPENDENT_CHARACTERISTIC")
                    for c in b.children
                ):
                    raise FormatError("虚拟或依赖标定对象不可直接编辑")
                layout = layouts.get(layout_name)
                if layout is None:
                    raise FormatError("缺少 RECORD_LAYOUT")
                lt = layout.tokens[1:]
                storage_key = "AXIS_PTS_X" if b.kind == "AXIS_PTS" else "FNC_VALUES"
                fnc = opt(lt, storage_key, 4)
                dirs = ("INDEX_INCR",) if b.kind == "AXIS_PTS" else ("ROW_DIR", "COLUMN_DIR")
                if not fnc or fnc[0] != "1" or fnc[3] != "DIRECT" or fnc[2] not in dirs:
                    raise FormatError("仅支持首项 FNC_VALUES、DIRECT 连续存储")
                # Reject record prefixes, rescaling, index indirection, and fixed offsets.
                if len(lt) != 5 or lt[0] != storage_key:
                    raise FormatError("复杂 RECORD_LAYOUT 尚未支持")
                p.dtype = fnc[1]
                if p.dtype not in TYPES:
                    raise FormatError(f"不支持的数据类型：{p.dtype}")
                order = opt(t[9:], "BYTE_ORDER", default=default_order)
                if order not in ("MSB_LAST", "MSB_FIRST"):
                    raise FormatError("字节序未定义或不支持，不能安全解码")
                p.endian = "<" if order == "MSB_LAST" else ">"
                if p.kind != "VALUE":
                    if "MATRIX_DIM" in t[9:]:
                        idx = t.index("MATRIX_DIM") + 1
                        dims = []
                        while idx < len(t) and len(dims) < 3 and re.fullmatch(r"\d+", t[idx]):
                            dims.append(int(t[idx]))
                            idx += 1
                        if not dims or min(dims) < 1:
                            raise FormatError("数组维度无效")
                        p.dimensions = tuple(dims)
                        p.count = math.prod(dims)
                    elif "NUMBER" in t[9:]:
                        p.count = int(opt(t[9:], "NUMBER"))
                        p.dimensions = (p.count,)
                    elif p.kind in ("CURVE", "MAP", "CUBOID", "CUBE_4", "CUBE_5"):
                        dims = []
                        axes = [c for c in b.children if c.kind == "AXIS_DESCR"]
                        for axis in axes:
                            at = axis.tokens
                            if len(at) < 6 or at[0] != "FIX_AXIS":
                                raise FormatError("曲线/表无 MATRIX_DIM 且不是明确的 FIX_AXIS")
                            fixed = opt(at[6:], "FIX_AXIS_PAR", 3) or opt(
                                at[6:], "FIX_AXIS_PAR_DIST", 3
                            )
                            if fixed:
                                dims.append(int(fixed[2]))
                            else:
                                lists = [c for c in axis.children if c.kind == "FIX_AXIS_PAR_LIST"]
                                if len(lists) != 1:
                                    raise FormatError("固定轴缺少元素数量")
                                dims.append(len(lists[0].tokens))
                        required = {"CURVE": 1, "MAP": 2, "CUBOID": 3, "CUBE_4": 4, "CUBE_5": 5}[
                            p.kind
                        ]
                        if len(dims) != required or min(dims) < 1:
                            raise FormatError("固定轴维度不完整")
                        p.dimensions, p.count = tuple(dims), math.prod(dims)
                    else:
                        raise FormatError("数组缺少 MATRIX_DIM / NUMBER")
                    if not 1 <= p.count <= 100000:
                        raise FormatError("数组规模超过 100000 元素限制")
                elif "MATRIX_DIM" in t[9:]:
                    raise FormatError("VALUE 携带数组维度：不猜测元素数量")
                if "BIT_MASK" in t[9:]:
                    p.mask = int(opt(t[9:], "BIT_MASK"), 0)
                    if TYPES[p.dtype] not in ("B", "H", "I", "Q"):
                        raise FormatError("位掩码仅支持无符号整数")
                    shift = (p.mask & -p.mask).bit_length() - 1
                    m = p.mask >> max(shift, 0)
                    if not p.mask or p.mask >= 2 ** (p.size * 8) or m & (m + 1):
                        raise FormatError("位掩码必须是范围内连续位")
                conv_name = t[6]
                if conv_name != "NO_COMPU_METHOD":
                    cb = methods.get(conv_name)
                    if not cb or len(cb.tokens) < 5:
                        raise FormatError(f"换算方法缺失：{conv_name}")
                    ct = cb.tokens
                    p.conversion = Conversion(ct[2], unquote(ct[4]))
                    cv = p.conversion
                    if cv.kind == "LINEAR":
                        vals = opt(ct[5:], "COEFFS_LINEAR", 2)
                        if not vals:
                            raise FormatError("缺少 COEFFS_LINEAR")
                        cv.coefficients = tuple(map(number, vals))
                        if cv.coefficients[0] == 0:
                            raise FormatError("换算斜率为零")
                    elif cv.kind == "RAT_FUNC":
                        vals = opt(ct[5:], "COEFFS", 6)
                        if not vals:
                            raise FormatError("缺少 COEFFS")
                        cv.coefficients = tuple(map(number, vals))
                        a, bb, cc, d, e, f = cv.coefficients
                        cv.domain = (p.low, p.high)
                        if d == e == f == 0:
                            raise FormatError("RAT_FUNC 分母恒为零")
                    elif cv.kind == "TAB_VERB":
                        table = tables.get(opt(ct[5:], "COMPU_TAB_REF"))
                        if table is None:
                            raise FormatError("缺少枚举表")
                        tt = table.tokens
                        count = int(tt[3])
                        if len(tt) < 4 + 2 * count:
                            raise FormatError("枚举表不完整")
                        cv.labels = {
                            number(tt[4 + 2 * i]): unquote(tt[5 + 2 * i]) for i in range(count)
                        }
                    elif cv.kind in ("TAB_INTP", "TAB_NOINTP"):
                        table = numeric_tables.get(opt(ct[5:], "COMPU_TAB_REF"))
                        if table is None or len(table.tokens) < 4:
                            raise FormatError("缺少数值换算表")
                        tt = table.tokens
                        count = int(tt[3])
                        if count < 1 or len(tt) < 4 + 2 * count:
                            raise FormatError("换算表长度错误")
                        cv.points = tuple(
                            sorted(
                                (number(tt[4 + 2 * i]), number(tt[5 + 2 * i])) for i in range(count)
                            )
                        )
                        xs, ys = zip(*cv.points)
                        if len(set(xs)) != count or not (
                            all(a < bb for a, bb in zip(ys, ys[1:]))
                            or all(a > bb for a, bb in zip(ys, ys[1:]))
                        ):
                            raise FormatError("数值换算表必须严格单调，避免逆变换歧义")
                    elif cv.kind != "IDENTICAL":
                        raise FormatError(f"暂不支持换算 {cv.kind}")
                unit = opt(t[9:], "PHYS_UNIT")
                if unit is not None:
                    p.conversion.unit = unquote(unit)
                if b.kind == "AXIS_PTS":
                    p.kind = "AXIS_PTS"
            except (ValueError, IndexError, KeyError, TypeError) as exc:
                p.problem = str(exc)
        names = [p.name for p in self.parameters]
        if len(names) != len(set(names)):
            raise FormatError("标定名称重复，不能安全编辑")
        if not names:
            raise FormatError("A2L 中没有 CHARACTERISTIC 标定对象")

    @classmethod
    def load(cls, path):
        """从磁盘读取并依次尝试支持的文本编码；不修改源 A2L。"""
        content = Path(path).read_bytes()
        for encoding in ("utf-8-sig", "gb18030", "cp1252"):
            try:
                return cls(content.decode(encoding))
            except UnicodeDecodeError:
                pass
        raise FormatError("无法识别 A2L 文本编码")
