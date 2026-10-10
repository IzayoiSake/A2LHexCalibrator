"""语言资源服务：界面只传文本键，不直接读取文件。

语言文件使用 UTF-8 JSON；占位符与 Python str.format 一致。EXE 旁的 locales
允许用户覆盖已知文本；缺失或无效项回退到随程序打包的对应语言资源。
"""

from __future__ import annotations

import json
import string
import sys
from functools import lru_cache
from importlib.resources import files
from pathlib import Path


class TranslationService:
    """每个窗口独立持有语言状态，避免全局语言污染测试或其他窗口。"""

    LANGUAGES = ("zh_CN", "en_US")

    def __init__(self, language="zh_CN", override_directory=None):
        self.catalogs = {}
        if override_directory is None and getattr(sys, "frozen", False):
            override_directory = Path(sys.executable).parent / "locales"
        for code in self.LANGUAGES:
            resource = files("a2l_hex_calibrator").joinpath("locales", code + ".json")
            catalog = json.loads(resource.read_text(encoding="utf-8"))
            if override_directory is not None:
                try:
                    override = json.loads(
                        (Path(override_directory) / (code + ".json")).read_text(encoding="utf-8")
                    )
                    for key, value in override.items():
                        if (
                            key in catalog
                            and isinstance(value, str)
                            and value
                            and self.fields(value) == self.fields(catalog[key])
                        ):
                            catalog[key] = value
                except (OSError, ValueError, AttributeError, TypeError):
                    pass
            self.catalogs[code] = catalog
        self.set_language(language)

    @staticmethod
    def fields(text):
        """比较占位符签名，拒绝翻译误删或误改参数。"""
        return {
            (field, spec, conversion)
            for _, field, spec, conversion in string.Formatter().parse(text)
            if field is not None
        }

    def set_language(self, language):
        """只接受已提供资源的语言，损坏的偏好值使用默认中文。"""
        self.language = language if language in self.LANGUAGES else "zh_CN"

    def text(self, key, **values):
        """通过稳定文本键查找资源；错误键显式报错，便于测试发现遗漏。"""
        return self.catalogs[self.language][key].format(**values)


@lru_cache(maxsize=1)
def default_translator():
    return TranslationService()


def default_text(key, **values):
    """供独立键位校验使用；不创建或导入 Tk 窗口。"""
    return default_translator().text(key, **values)
