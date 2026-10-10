"""HEX 保存事务：先验证源文件，再写临时文件、读回、最后替换目标。
保留原文件保护；临时文件与目标同目录以避免跨卷替换。"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from ..errors import FormatError


class HexWriter:
    """专门负责固件输出，领域对象不直接管理磁盘写入。"""

    @staticmethod
    def save(session, path, source_path=None, overwrite=False):
        """overwrite 仅在界面获得覆盖确认后传入；失败时清理临时文件。"""
        if session.image is None:
            raise FormatError("请先加载 HEX")
        destination = Path(path)
        if source_path:
            source = Path(source_path)
            if destination.resolve() == source.resolve() or (
                destination.exists() and destination.samefile(source)
            ):
                raise FormatError("禁止覆盖原 HEX，请使用新文件名")
            if hashlib.sha256(source.read_bytes()).hexdigest() != session.image.digest:
                raise FormatError("原 HEX 在加载后发生变化，请重新加载")
        if destination.exists() and not overwrite:
            raise FormatError("目标文件已存在；请选择尚不存在的新文件名")
        output, records = session.image.render(session.patch())
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=destination.parent, delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(output)
                stream.flush()
                os.fsync(stream.fileno())
            if temporary.read_bytes() != output:
                raise FormatError("保存后读回不一致，文件可能受到加密软件影响")
            if overwrite:
                os.replace(temporary, destination)
            else:
                # On Windows rename refuses an existing target, including races.
                os.rename(temporary, destination)
            if destination.read_bytes() != output:
                raise FormatError("目标文件读回不一致，文件可能受到加密软件影响")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return {
            "changed_parameters": sum(e.changed for e in session.entries),
            "changed_bytes": len(session.patch()),
            "changed_records": records,
            "sha256": hashlib.sha256(output).hexdigest(),
        }
