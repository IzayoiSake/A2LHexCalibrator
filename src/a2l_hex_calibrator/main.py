"""应用启动入口；可执行 python -m a2l_hex_calibrator。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from . import A2L, HexImage, Session
from .ui.editor import Editor


def main():
    """设置 Windows DPI、创建主窗口；smoke-test 模式仅加载验证并自动退出。"""
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    app = Editor()
    # Non-interactive smoke test exercises a real Tk window and real sample loading.
    if len(sys.argv) == 5 and sys.argv[1] == "--smoke-test":
        app.withdraw()
        try:
            app.a2l_path, app.hex_path = Path(sys.argv[2]), Path(sys.argv[3])
            app.a2l = A2L.load(app.a2l_path)
            app.image = HexImage(app.hex_path.read_bytes())
            app.session = Session(app.a2l, app.image)
            app.refresh()
            app.update()
            result = {
                "ok": True,
                "objects": len(app.a2l.parameters),
                "rows": len(app.tree.get_children()),
            }
            app.query.set("*Vbus*")
            app.refresh()
            result["search_rows"] = len(app.tree.get_children())
            Path(sys.argv[4]).write_text(json.dumps(result), encoding="utf-8")
        except Exception as exc:
            Path(sys.argv[4]).write_text(
                json.dumps({"ok": False, "error": str(exc)}), encoding="utf-8"
            )
            raise
        finally:
            app.destroy()
        return
    app.mainloop()
