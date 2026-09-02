#!/usr/bin/env python3
"""Merge reviewed Chinese translations into formatted Tropica layout data."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final


ROOT: Final = Path(__file__).resolve().parents[1]
RAW_PATH: Final = ROOT / "raw" / "tropica.com" / "layout-detail-list.json"
TRANSLATIONS_PATH: Final = ROOT / "scripts" / "layout-translations.json"
OUTPUT_PATH: Final = ROOT / "formatted" / "layout-detail-list.json"
DIFFICULTY_CN: Final = {
    "Easy": "简单",
    "Medium": "中等",
    "Advanced": "困难",
}
PASSTHROUGH_TECHNIQUE_KEYS: Final = {
    "aquarium",
    "light",
    "substrate",
    "gravel",
    "filter",
    "co2",
}
PROMPT_LEAK_RE: Final = re.compile(
    r"这是.{0,100}(?:字段|参数)|水草缸参数|请翻译|译文[：:]|"
    r"输入(?:内容)?(?:为)?[：:]|解释[：:]|"
    r"(?:水族箱|造景缸)(?:的)?型号或尺寸[：:]|"
    r"(?:过滤器|滤材)配置[：:]|^造景素材\s*[：:]|"
    r"^每周施肥配置\s*[：:]|请使用",
    re.I,
)


def write_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_existing_local_paths() -> dict[str, tuple[list[str], str]]:
    if not OUTPUT_PATH.exists():
        return {}
    payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    return {
        item["layout_id"]: (
            item.get("local_images", []),
            item.get("local_planting_plan", ""),
        )
        for item in payload.get("detail_list", [])
    }


def validate_translation(raw: dict, translated: dict) -> None:
    required = {
        "name_cn",
        "difficulty_cn",
        "technique_cn",
        "descriptions_cn",
    }
    missing = sorted(required - set(translated))
    if missing:
        raise ValueError(f"{raw['layout_id']}: missing translations {missing}")
    expected_difficulty = DIFFICULTY_CN[raw["difficulty"]]
    if translated["difficulty_cn"] != expected_difficulty:
        raise ValueError(
            f"{raw['layout_id']}: difficulty_cn must be {expected_difficulty!r}"
        )
    if set(translated["technique_cn"]) != set(raw["technique"]):
        raise ValueError(f"{raw['layout_id']}: technique_cn keys do not match source")
    for key, source_value in raw["technique"].items():
        target_value = translated["technique_cn"][key]
        if bool(source_value) != bool(target_value):
            raise ValueError(
                f"{raw['layout_id']}: empty-state mismatch for technique_cn.{key}"
            )
        if key in PASSTHROUGH_TECHNIQUE_KEYS and target_value != source_value:
            raise ValueError(
                f"{raw['layout_id']}: technique_cn.{key} must preserve the raw "
                "brand/model/specification value"
            )
        if PROMPT_LEAK_RE.search(target_value):
            raise ValueError(
                f"{raw['layout_id']}: prompt text leaked into technique_cn.{key}"
            )
    if len(translated["descriptions_cn"]) != len(raw["descriptions"]):
        raise ValueError(
            f"{raw['layout_id']}: descriptions_cn count does not match source"
        )
    if not translated["name_cn"].strip():
        raise ValueError(f"{raw['layout_id']}: name_cn is empty")
    if any(not value.strip() for value in translated["descriptions_cn"]):
        raise ValueError(f"{raw['layout_id']}: descriptions_cn contains an empty value")
    translated_prose = [translated["name_cn"], *translated["descriptions_cn"]]
    if any(PROMPT_LEAK_RE.search(value) for value in translated_prose):
        raise ValueError(f"{raw['layout_id']}: prompt text leaked into translated prose")


def main() -> None:
    raw_payload = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    translations = json.loads(TRANSLATIONS_PATH.read_text(encoding="utf-8"))
    raw_items = raw_payload["detail_list"]
    raw_ids = {item["layout_id"] for item in raw_items}
    translation_ids = set(translations)
    if raw_ids != translation_ids:
        missing = sorted(raw_ids - translation_ids)
        unexpected = sorted(translation_ids - raw_ids)
        raise ValueError(
            f"translation ID mismatch; missing={missing}, unexpected={unexpected}"
        )

    existing_paths = load_existing_local_paths()
    formatted_items: list[dict] = []
    for raw in raw_items:
        translated = translations[raw["layout_id"]]
        validate_translation(raw, translated)
        local_images, local_planting_plan = existing_paths.get(
            raw["layout_id"], ([], "")
        )
        formatted_items.append(
            {
                **raw,
                "name_cn": translated["name_cn"],
                "difficulty_cn": translated["difficulty_cn"],
                "technique_cn": translated["technique_cn"],
                "descriptions_cn": translated["descriptions_cn"],
                "local_images": local_images,
                "local_planting_plan": local_planting_plan,
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_PATH, {"detail_list": formatted_items})
    print(f"wrote {len(formatted_items)} formatted layouts to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
