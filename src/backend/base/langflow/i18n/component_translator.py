"""
component_translator.py
后端组件定义翻译器（方案 A：后端 i18n 支持）

使用方式：
    from langflow.i18n.component_translator import translate_component_dict
    translated = translate_component_dict(all_types, "zh-CN")
"""

from __future__ import annotations

import copy
from typing import Any


def translate_component_dict(all_types: dict[str, Any], lang: str) -> dict[str, Any]:
    """对 /api/v1/all 返回的组件字典做语言翻译。

    Args:
        all_types: 原始组件字典（三层嵌套：category → component_type → APIClassType）
        lang: 目标语言（当前支持 "zh-CN"，其他语言直接返回原始数据）

    Returns:
        翻译后的组件字典（深拷贝，不修改原始数据）
    """
    if not lang.startswith("zh"):
        return all_types

    from langflow.i18n.zh_cn_translations import (
        FIELD_DISPLAY_NAMES,
        NODE_DESCRIPTIONS,
        NODE_DISPLAY_NAMES,
        OUTPUT_DISPLAY_NAMES,
    )

    # 深拷贝避免修改缓存中的原始数据
    result = copy.deepcopy(all_types)

    for _category, components in result.items():
        if not isinstance(components, dict):
            continue
        for _comp_type, comp_data in components.items():
            if not isinstance(comp_data, dict):
                continue

            # 翻译节点 display_name
            if "display_name" in comp_data:
                comp_data["display_name"] = NODE_DISPLAY_NAMES.get(
                    comp_data["display_name"], comp_data["display_name"]
                )

            # 翻译节点 description
            if "description" in comp_data:
                comp_data["description"] = NODE_DESCRIPTIONS.get(
                    comp_data["description"], comp_data["description"]
                )

            # 翻译 template 字段
            template = comp_data.get("template", {})
            if isinstance(template, dict):
                for _field_key, field_data in template.items():
                    if not isinstance(field_data, dict):
                        continue
                    # 翻译字段 display_name
                    if "display_name" in field_data:
                        field_data["display_name"] = FIELD_DISPLAY_NAMES.get(
                            field_data["display_name"], field_data["display_name"]
                        )

            # 翻译 outputs 列表
            outputs = comp_data.get("outputs", [])
            if isinstance(outputs, list):
                for output in outputs:
                    if isinstance(output, dict) and "display_name" in output:
                        output["display_name"] = OUTPUT_DISPLAY_NAMES.get(
                            output["display_name"], output["display_name"]
                        )

    return result
