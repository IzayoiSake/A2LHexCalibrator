"""Intel HEX 无损解析与补丁渲染；保留记录顺序、换行和未修改字符。"""

from __future__ import annotations

import bisect
import hashlib
import re
from dataclasses import dataclass
from ..errors import FormatError


@dataclass
class Record:
    """数据记录及其原始行位置，确保只在对应字符范围内修改。"""

    line: int
    offset: int
    address: int
    data: bytes
    encoded: bytes


class HexImage:
    """只读原始镜像；render 返回新内容，不修改加载时的原始缓冲区。"""

    def __init__(self, content: bytes):
        """验证记录长度、校验和、地址边界和 EOF；相同地址仅接受一致的数据副本。"""
        self.content = content
        self.digest = hashlib.sha256(content).hexdigest()
        self.lines = content.splitlines(keepends=True)
        self.records: list[Record] = []
        base = 0
        eof = False
        for number, line in enumerate(self.lines):
            body = line.strip(b" \t\r\n")
            if eof:
                if body.strip(b"\x1a \t\r\n"):
                    raise FormatError(f"HEX 第 {number + 1} 行：EOF 后存在非填充内容")
                continue
            if not body:
                continue
            if not re.fullmatch(rb":[0-9a-fA-F]+", body):
                raise FormatError(f"HEX 第 {number + 1} 行：不是 Intel HEX 记录")
            try:
                raw = bytes.fromhex(body[1:].decode("ascii"))
            except ValueError as exc:
                raise FormatError(f"HEX 第 {number + 1} 行：十六进制长度错误") from exc
            if len(raw) < 5 or len(raw) != raw[0] + 5 or sum(raw) & 255:
                raise FormatError(f"HEX 第 {number + 1} 行：长度或校验和错误")
            count, typ = raw[0], raw[3]
            address = int.from_bytes(raw[1:3], "big")
            data = raw[4:-1]
            if typ == 0:
                if address + count > 65536 or base + address + count > 2**32:
                    raise FormatError("HEX 数据记录跨地址边界")
                if count:
                    self.records.append(Record(number, line.index(b":"), base + address, data, raw))
            elif typ == 1:
                if count or address:
                    raise FormatError("HEX EOF 记录不合法")
                eof = True
            elif typ in (2, 4):
                if count != 2 or address:
                    raise FormatError("HEX 扩展地址记录不合法")
                base = int.from_bytes(data, "big") << (4 if typ == 2 else 16)
            elif typ in (3, 5):
                if count != 4 or address:
                    raise FormatError("HEX 入口地址记录不合法")
            else:
                raise FormatError(f"不支持的 HEX 记录类型：{typ}")
        if not eof:
            raise FormatError("HEX 缺少 EOF 记录")
        if not self.records:
            raise FormatError("HEX 不含数据记录")
        # Merge for fast reads, accepting only identical overlapping bytes.
        self.segments: list[tuple[int, bytearray]] = []
        for rec in sorted(self.records, key=lambda r: r.address):
            if not self.segments or rec.address > self.segments[-1][0] + len(self.segments[-1][1]):
                self.segments.append((rec.address, bytearray(rec.data)))
                continue
            start, buf = self.segments[-1]
            offset = rec.address - start
            overlap = min(len(rec.data), len(buf) - offset)
            if buf[offset : offset + overlap] != rec.data[:overlap]:
                raise FormatError(f"HEX 重叠地址数据冲突：0x{rec.address:X}")
            buf.extend(rec.data[overlap:])
        self.starts = [s for s, _ in self.segments]

    def read(self, address: int, size: int) -> bytes:
        """按绝对地址读取连续数据；缺失地址报错，绝不自动补零。"""
        i = bisect.bisect_right(self.starts, address) - 1
        if i < 0:
            raise FormatError(f"HEX 无此地址：0x{address:08X}")
        start, data = self.segments[i]
        offset = address - start
        if offset + size > len(data):
            raise FormatError(f"HEX 数据不完整：0x{address:08X}，需要 {size} 字节")
        return bytes(data[offset : offset + size])

    def render(self, changes: dict[int, int]) -> tuple[bytes, int]:
        """应用字节补丁、重算受影响行校验和，再完整重解析并验证未授权字节未变。"""
        changes = {a: v for a, v in changes.items() if self.read(a, 1)[0] != v}
        if not changes:
            return self.content, 0
        for v in changes.values():
            if not isinstance(v, int) or not 0 <= v <= 255:
                raise FormatError("待写入值不是字节")
        addresses = sorted(changes)
        lines = list(self.lines)
        affected = 0
        for rec in self.records:
            lo = bisect.bisect_left(addresses, rec.address)
            hi = bisect.bisect_left(addresses, rec.address + len(rec.data))
            if lo == hi:
                continue
            encoded = bytearray(rec.encoded)
            line = bytearray(lines[rec.line])
            for address in addresses[lo:hi]:
                idx = address - rec.address
                encoded[4 + idx] = changes[address]
                pos = rec.offset + 9 + 2 * idx
                old = bytes(line[pos : pos + 2])
                value = f"{changes[address]:02X}".encode()
                if any(c in b"abcdef" for c in old):
                    value = value.lower()
                line[pos : pos + 2] = value
            encoded[-1] = (-sum(encoded[:-1])) & 255
            pos = rec.offset + 9 + 2 * len(rec.data)
            old = bytes(line[pos : pos + 2])
            value = f"{encoded[-1]:02X}".encode()
            line[pos : pos + 2] = value.lower() if any(c in b"abcdef" for c in old) else value
            lines[rec.line] = bytes(line)
            affected += 1
        output = b"".join(lines)
        check = HexImage(output)
        if len(check.records) != len(self.records):
            raise FormatError("保存校验失败：记录数量变化")
        for old, new in zip(self.records, check.records):
            if (old.address, len(old.data), old.line) != (new.address, len(new.data), new.line):
                raise FormatError("保存校验失败：记录结构变化")
            expected = bytes(changes.get(old.address + i, v) for i, v in enumerate(old.data))
            if expected != new.data:
                raise FormatError("保存校验失败：参数范围之外的数据发生变化")
        return output, affected
