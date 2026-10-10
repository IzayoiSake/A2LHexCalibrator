"""A2L 词法和块结构：语法树与标定对象语义解析分离。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from ..errors import FormatError


@dataclass
class Block:
    """记录块类型、普通 token 和嵌套子块。"""

    kind: str
    tokens: list[str] = field(default_factory=list)
    children: list["Block"] = field(default_factory=list)


def unquote(value: str) -> str:
    """解码 A2L 带引号文本及转义字符。"""
    if value.startswith('"'):
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def opt(tokens, key, count=1, default=None):
    """读取指定可选关键字的参数；关键字存在但参数不完整时立即报错。"""
    try:
        i = tokens.index(key) + 1
    except ValueError:
        return default
    if i + count > len(tokens):
        raise FormatError(f"{key} 定义不完整")
    return tokens[i] if count == 1 else tokens[i : i + count]


class A2LBlockParser:
    """ASAP2 块语法解析器；不承担类型/地址等语义判断。"""

    @staticmethod
    def parse(text: str) -> Block:
        # AML is a separate grammar; it cannot affect calibration storage definitions.
        """忽略注释及独立 A2ML 语法，用栈验证 begin/end 成对匹配。"""
        text = re.sub(r"/begin\s+A2ML\b.*?/end\s+A2ML\b", "", text, flags=re.S)
        scanner = re.compile(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*|/begin\b|/end\b|[^\s]+', re.S)
        tokens = [
            m.group() for m in scanner.finditer(text) if not m.group().startswith(("/*", "//"))
        ]
        root = Block("ROOT")
        stack = [root]
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token == "/begin":
                i += 1
                if i == len(tokens):
                    raise FormatError("A2L /begin 不完整")
                block = Block(tokens[i])
                stack[-1].children.append(block)
                stack.append(block)
            elif token == "/end":
                i += 1
                if i == len(tokens) or len(stack) == 1 or stack[-1].kind != tokens[i]:
                    raise FormatError("A2L 块边界不匹配")
                stack.pop()
            else:
                stack[-1].tokens.append(token)
            i += 1
        if len(stack) != 1:
            raise FormatError("A2L 存在未关闭的块")
        return root
