"""EXE 集成冒烟：临时合成数据，验证启动、加载及搜索，不触碰客户固件。"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile

from tests.fixtures import description, session


def main():
    executable = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        a2l = root / "sample.a2l"
        hex_file = root / "sample.hex"
        report = root / "smoke.json"
        a2l.write_text(description(name="Device1_Mon_Vbus"), encoding="utf-8")
        hex_file.write_bytes(session().image.content)
        subprocess.run(
            [str(executable), "--smoke-test", str(a2l), str(hex_file), str(report)],
            check=True,
            timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        result = json.loads(report.read_text(encoding="utf-8"))
        assert result == {"ok": True, "objects": 1, "rows": 1, "search_rows": 1}, result
        print(json.dumps(result))


if __name__ == "__main__":
    main()
