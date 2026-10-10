"""架构约束回归：避免后续迭代把业务逻辑或磁盘操作塞回界面。"""

import ast
from pathlib import Path
import subprocess
import sys
import unittest


class ArchitectureTests(unittest.TestCase):
    def test_backend_import_does_not_load_tkinter(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                'import sys; import a2l_hex_calibrator.backend; assert "tkinter" not in sys.modules',
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_backend_has_no_ui_dependency(self):
        root = Path(__file__).resolve().parents[1] / "src/a2l_hex_calibrator/backend"
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [name.name for name in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                else:
                    continue
                for module in modules:
                    with self.subTest(path=path.name, module=module):
                        self.assertNotIn("tkinter", module)
                        self.assertNotIn("ui", module.split("."))

    def test_ui_does_not_write_files_or_pending_bytes(self):
        root = Path(__file__).resolve().parents[1] / "src/a2l_hex_calibrator/ui"
        forbidden = {
            "read_text",
            "read_bytes",
            "write_text",
            "write_bytes",
            "open",
            "unlink",
            "mkdir",
            "rename",
            "replace",
            "NamedTemporaryFile",
        }
        for path in root.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call):
                    name = (
                        node.func.attr
                        if isinstance(node.func, ast.Attribute)
                        else getattr(node.func, "id", "")
                    )
                    with self.subTest(path=path.name, call=name):
                        self.assertNotIn(name, forbidden)
                if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
                    self.assertNotEqual(node.attr, "pending", path.name)
