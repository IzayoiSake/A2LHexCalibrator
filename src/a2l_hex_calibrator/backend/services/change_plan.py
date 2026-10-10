"""名称驱动的 JSON 修改方案；不持久化地址，允许新版本重新匹配。"""

from __future__ import annotations

import json
from ..errors import FormatError


class ChangePlanCodec:
    """方案序列化与整批验证；导入返回待应用集合，不直接修改会话。"""

    @staticmethod
    def export(session):
        """仅导出已修改项的名称、物理值和单位，保留人可读的 JSON 缩进。"""
        parameters = {}
        for entry in session.entries:
            if entry.changed:
                if entry.name in parameters:
                    raise FormatError(f"参数名称不唯一：{entry.name}")
                parameters[entry.name] = {
                    "value": entry.display(),
                    "mode": "physical",
                    "unit": entry.parameter.conversion.unit,
                }
        return (
            json.dumps(
                {"format": "A2LHexEditor.changes", "version": 1, "parameters": parameters},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )

    @staticmethod
    def prepare_import(session, text):
        """拒绝重复名称、单位不一致和非法数值；所有项通过后才返回修改集合。"""

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise FormatError(f"JSON 重复名称：{key}")
                result[key] = value
            return result

        data = json.loads(text, object_pairs_hook=unique)
        if (
            not isinstance(data, dict)
            or data.get("format") != "A2LHexEditor.changes"
            or data.get("version") != 1
        ):
            raise FormatError("不是支持的修改方案格式 / 版本")
        parameters = data.get("parameters")
        if not isinstance(parameters, dict):
            raise FormatError("parameters 必须是按参数名索引的对象")
        by_name = {}
        for entry in session.entries:
            by_name.setdefault(entry.name, []).append(entry)
        changes, errors = [], []
        for name, item in parameters.items():
            try:
                matches = by_name.get(name, [])
                if len(matches) != 1:
                    raise FormatError("当前 A2L 无此参数" if not matches else "当前 A2L 名称不唯一")
                entry = matches[0]
                if not isinstance(item, dict) or item.get("mode") not in ("physical", "raw"):
                    raise FormatError("每项需包含 value、mode（physical 或 raw）")
                value = item.get("value")
                if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                    raise FormatError("value 必须为字符串或数值，推荐字符串以保留精度")
                if (
                    item["mode"] == "physical"
                    and item.get("unit") != entry.parameter.conversion.unit
                ):
                    raise FormatError("物理单位与当前 A2L 不一致，请核对方案中的 unit")
                changes.append(
                    (entry, session.validate_value(entry, str(value), item["mode"] == "raw"))
                )
            except (ValueError, OverflowError) as exc:
                errors.append(f"{name}: {exc}")
        if errors:
            raise FormatError("方案未应用；请修正以下问题后重新加载：\n" + "\n".join(errors))
        return changes
