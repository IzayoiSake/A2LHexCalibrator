"""以隔离设置启动真实 EXE，验证中文及英文均能加载资源、文件并搜索。"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from tests.fixtures import description, session


def main():
    executable = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        a2l, hex_file, report = root / "sample.a2l", root / "sample.hex", root / "report.json"
        a2l.write_text(description(name="Device1_Mon_Vbus"), encoding="utf-8")
        hex_file.write_bytes(session().image.content)
        settings = root / "A2LHexEditor" / "shortcuts.json"
        settings.parent.mkdir()
        for language in ("zh_CN", "en_US"):
            settings.write_text(json.dumps({"language": language}), encoding="utf-8")
            subprocess.run(
                [str(executable), "--smoke-test", str(a2l), str(hex_file), str(report)],
                check=True,
                timeout=45,
                creationflags=subprocess.CREATE_NO_WINDOW,
                env={**os.environ, "APPDATA": str(root)},
            )
            result = json.loads(report.read_text(encoding="utf-8"))
            assert result == {"ok": True, "objects": 1, "rows": 1, "search_rows": 1}, result
            print(language, json.dumps(result))


if __name__ == "__main__":
    main()
