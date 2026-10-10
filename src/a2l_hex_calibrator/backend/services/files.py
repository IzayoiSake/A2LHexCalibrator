"""文件应用服务：UI 传入路径和普通数据，不直接读写磁盘。"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path

from ..errors import FormatError
from ..formats.a2l import A2L
from ..formats.intel_hex import HexImage


class FileService:
    """封装文件加载、方案和设置存储；无需 Tk，可用于脚本或其他 UI。"""

    @staticmethod
    def path(value):
        """统一路径对象；不读取文件。"""
        return Path(value)

    @staticmethod
    def exists(path):
        """供界面决定是否展示覆盖确认。"""
        return Path(path).exists()

    @staticmethod
    def load_pair(kind, path, a2l=None, image=None):
        """加载一个文件并使用另一侧的现有数据重建会话，失败不影响旧会话。"""
        # 延迟导入以避免 Session 与持久化服务形成模块导入环。
        from ..domain.session import Session

        if kind not in ("a2l", "hex"):
            raise ValueError("文件类型只能为 a2l 或 hex")
        data = A2L.load(path) if kind == "a2l" else HexImage(Path(path).read_bytes())
        a2l = data if kind == "a2l" else a2l
        image = data if kind == "hex" else image
        return data, Session(a2l, image) if a2l else None

    @staticmethod
    def write_text_atomic(path, content):
        """同目录写临时文件并校验后替换，不先截断已有目标。"""
        destination = Path(path)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=destination.parent,
                prefix=".calibration-",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if temporary.read_text(encoding="utf-8") != content:
                raise FormatError("临时文件读回不一致，原文件未覆盖")
            os.replace(temporary, destination)
            if destination.read_text(encoding="utf-8") != content:
                raise FormatError("保存后读回不一致，请检查文件加密软件")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @classmethod
    def save_plan(cls, path, session):
        """保存人可读、无地址的修改方案；覆盖确认由 UI 负责。"""
        cls.write_text_atomic(path, session.export_changes())

    @staticmethod
    def load_plan(path, session):
        """读取并完整校验方案；返回待应用项，不修改会话。"""
        return session.import_changes(Path(path).read_text(encoding="utf-8-sig"))

    @staticmethod
    def export_csv(path, rows):
        """导出普通字符串行，转义公式前缀；保持原有 CSV 不覆盖策略。"""
        with Path(path).open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["名称", "地址", "存储类型", "原值", "当前值", "单位", "状态", "说明"])
            for row in rows:
                writer.writerow(
                    [
                        "'" + value if value.startswith(("=", "+", "-", "@")) else value
                        for value in row
                    ]
                )

    @staticmethod
    def settings_path(path=None):
        """兼容旧版配置目录，重命名应用不丢失用户已配置的快捷键。"""
        return (
            Path(path)
            if path
            else Path(os.getenv("APPDATA", str(Path.home()))) / "A2LHexEditor" / "shortcuts.json"
        )

    @staticmethod
    def read_settings(path):
        """读取设置字典，键位合法性仍由纯配置规则校验。"""
        return json.loads(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def write_settings(cls, path, mapping):
        """创建用户设置目录，并通过统一安全文本写入流程保存。"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        cls.write_text_atomic(path, json.dumps(mapping, ensure_ascii=False, indent=2))
