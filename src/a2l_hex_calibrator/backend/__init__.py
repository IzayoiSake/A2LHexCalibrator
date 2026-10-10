"""离线标定编辑公共接口；导入本包不会创建 GUI 或连接设备。"""

from .errors import FormatError
from .formats.a2l import A2L
from .formats.intel_hex import HexImage
from .domain.session import Session
from .services.search import SearchQuery, search_matches

__all__ = ["A2L", "HexImage", "Session", "FormatError", "SearchQuery", "search_matches"]
