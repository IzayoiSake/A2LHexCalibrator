"""与 Tk 无关的尺寸计算，输入为显示器工作区四边坐标。"""

from __future__ import annotations


def startup_bounds(work_area):
    """返回工作区 75% 宽高及居中坐标；支持负坐标副屏。"""
    left, top, right, bottom = work_area
    width = max(1, round((right - left) * 0.75))
    height = max(1, round((bottom - top) * 0.75))
    return width, height, left + (right - left - width) // 2, top + (bottom - top - height) // 2
