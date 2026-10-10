"""统一的可预期业务异常；界面捕获后向用户展示，不静默修复固件。"""

from __future__ import annotations


class FormatError(ValueError):
    """文件格式、数据范围或安全校验不满足要求。"""

    pass
