"""变量搜索：使用标准库 fnmatch，不维护自制正则通配符引擎。"""

from __future__ import annotations

import fnmatch
from ..domain.entry import Entry


class SearchQuery:
    """一次查询复用于多行；名称和描述均匹配，忽略大小写及首尾空白。"""

    def __init__(self, pattern: str):
        self.pattern = pattern.strip().casefold()
        self.has_wildcard = "*" in self.pattern or "?" in self.pattern
        # 两侧补星号实现包含搜索；方括号保持数组下标字面含义。
        self.glob = "*" + self.pattern.replace("[", "[[]") + "*"

    def matches(self, entry: Entry) -> bool:
        """空查询接受所有行；普通文字用包含，通配符交给 fnmatch。"""
        values = (entry.name.casefold(), entry.parameter.description.casefold())
        if not self.has_wildcard:
            return any(self.pattern in value for value in values)
        return any(fnmatch.fnmatchcase(value, self.glob) for value in values)


def search_matches(entry: Entry, pattern: str) -> bool:
    """单项查询便捷接口；表格批量筛选优先复用一个 SearchQuery。"""
    return SearchQuery(pattern).matches(entry)
