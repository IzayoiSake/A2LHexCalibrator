"""键位定义及纯校验函数；不依赖窗口，方便单元测试。"""

from __future__ import annotations
from ..backend.services.translation import default_text

DEFAULT_KEYS = {
    "load_a2l": "Ctrl+O",
    "load_hex": "Ctrl+Shift+O",
    "edit": "F2",
    "revert": "Ctrl+R",
    "undo": "Ctrl+Z",
    "preview": "Ctrl+P",
    "export": "Ctrl+E",
    "help": "F1",
    "save": "Ctrl+Shift+S",
    "save_plan": "Ctrl+S",
    "load_plan": "Ctrl+L",
    "search": "Ctrl+F",
    "select_all": "Ctrl+A",
    "confirm": "Enter",
    "cancel": "Esc",
}


def normalize_key(text, translate=default_text):
    """统一按键别名、修饰键顺序和大小写，拒绝会干扰普通输入的配置。"""
    parts = [part.strip().lower() for part in text.split("+")]
    if not text.strip():
        return ""
    modifiers = parts[:-1]
    if len(set(modifiers)) != len(modifiers) or any(
        m not in ("ctrl", "alt", "shift") for m in modifiers
    ):
        raise ValueError(translate("keymap.invalid_shortcut_format_p0", p0=text))
    key = parts[-1]
    key = {"return": "enter", "escape": "esc"}.get(key, key)
    if not (
        key in ("enter", "esc", "delete", "space")
        or (len(key) == 1 and key.isascii() and key.isalnum())
        or key in [f"f{i}" for i in range(1, 13)]
    ):
        raise ValueError(translate("keymap.unsupported_key_p0", p0=text))
    if len(key) == 1 and not any(m in modifiers for m in ("ctrl", "alt")):
        raise ValueError(
            translate("keymap.letter_digit_shortcuts_must_include_ctrl_or_alt_to_pres")
        )
    return "+".join(
        [m.title() for m in ("ctrl", "alt", "shift") if m in modifiers]
        + [
            {"enter": "Enter", "esc": "Esc", "delete": "Delete", "space": "Space"}.get(
                key, key.upper()
            )
        ]
    )


def validate_keys(mapping, translate=default_text):
    """合并默认键位，拒绝冲突和占用剪贴板保留键。"""
    result = {
        name: normalize_key(mapping.get(name, default), translate)
        for name, default in DEFAULT_KEYS.items()
    }
    used = {}
    for name, key in result.items():
        if key and key in used:
            raise ValueError(
                translate("keymap.shortcut_conflict_p0_p1_p2", p0=key, p1=used[key], p2=name)
            )
        if key in ("Ctrl+C", "Ctrl+V", "Ctrl+X"):
            raise ValueError(translate("keymap.p0_is_reserved_for_copy_paste_and_cut", p0=key))
        if key:
            used[key] = name
    return result
