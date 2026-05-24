"""data.go.kr 응답 정규화 helper."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import Any

SECRET_KEYS = {"servicekey", "service_key", "apikey", "api_key", "key"}


def without_none(params: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value is not None}


def public_params(params: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: "***" if key.lower() in SECRET_KEYS else value
        for key, value in params.items()
        if value is not None
    }


def mask_params(params: Mapping[str, Any]) -> dict[str, Any]:
    return public_params(params)


def redact_secret(text: str, secret: str) -> str:
    if not secret:
        return text
    return text.replace(secret, "***")


def to_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def normalize_items(value: Any) -> list[dict[str, Any]]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        item = value.get("item")
        if item is not None:
            return normalize_items(item)
        return [value]
    return []


def xml_to_dict(text: str) -> dict[str, Any]:
    root = ET.fromstring(text)
    return {_strip_ns(root.tag): _element_to_value(root)}


def _element_to_value(element: ET.Element) -> Any:
    children = list(element)
    if not children:
        return (element.text or "").strip()

    result: dict[str, Any] = {}
    for child in children:
        key = _strip_ns(child.tag)
        value = _element_to_value(child)
        if key in result:
            current = result[key]
            if not isinstance(current, list):
                result[key] = [current]
            result[key].append(value)
        else:
            result[key] = value
    return result


def _strip_ns(tag: str) -> str:
    return re.sub(r"^\{.*\}", "", tag)
