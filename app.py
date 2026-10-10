"""源码/PyInstaller 启动壳；业务代码全部位于 src/a2l_hex_calibrator。"""

import sys
from pathlib import Path

# 源码直接启动时找到 src 布局；打包后模块由 PyInstaller 自带的导入器加载。
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from a2l_hex_calibrator.main import main

if __name__ == "__main__":
    main()
