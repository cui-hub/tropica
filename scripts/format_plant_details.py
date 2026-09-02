#!/usr/bin/env python3
"""Build translated Tropica plant details from the raw detail data."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DETAIL_PATH = ROOT / "raw" / "tropica.com" / "plant-detail-list.json"
FORMATTED_LIST_PATH = ROOT / "formatted" / "plant-list.json"
OUTPUT_PATH = ROOT / "formatted" / "plant-detail-list.json"
TRANSLATION_CACHE_PATH = ROOT / "scripts" / "detail-introduction-translations.json"

ORIGIN_CN = {
    "": "",
    "Africa": "非洲",
    "Asia": "亚洲",
    "Australia": "澳大利亚",
    "Cosmopolitan": "世界广布",
    "Cultivar": "栽培品种",
    "Europe/Asia": "欧洲／亚洲",
    "North America": "北美洲",
    "South America": "南美洲",
}

PROPERTY_DESCRIPTION_CN = {
    "type": "",
    "origin": "水草最常见的国家或洲。栽培品种是在人工环境中出现或选育而成的。",
    "growth_rate": "与其他水草相比，该水草的生长速度。",
    "height": "水草入缸两个月后的平均高度（厘米）。",
    "light_requirement": "水草的平均或中等光照需求约为 0.5 W/L。",
    "co2_requirement": "中等 CO₂ 需求为 6-14 mg/L，高需求约为 15-25 mg/L。",
    "type_cn": "",
    "origin_cn": "水草最常见的国家或洲。栽培品种是在人工环境中出现或选育而成的。",
}

GENUS_CN = {
    "Alternanthera": "血心兰",
    "Anubias": "水榕",
    "Bolbitis": "黑木蕨",
    "Bucephalandra": "辣椒榕",
    "Cryptocoryne": "椒草",
    "Echinodorus": "皇冠草",
    "Microsorum": "铁皇冠",
}

INTRODUCTION_OVERRIDES_BY_NAME = {
    "Alternanthera reineckii 'Mini'": "迷你血心兰采用密封杯组织培养，是常见血心兰的小型品种。它株型紧凑、生长较慢，适合小型水族箱，也可在大型造景中作前景草。通过定期修剪可形成约 5-10 厘米高的红紫色草坪。较强光照并补充 CO₂，有助于水草生长和发色。",
    "Anubias barteri ’Coin Leaf’": "金钱榕是水榕的栽培品种，叶片近圆形，直径约 4-6 厘米，呈深绿色。它生长缓慢并横向匍匐，弱光下也能正常生长，养护要求不高。可固定在石材或沉木上；若种入底床，根茎必须露出，否则容易腐烂。",
    "Anubias barteri var. nana ’Kirin’": "麒麟小榕是水榕的栽培品种，深绿色卵形叶片长约 3-4 厘米，叶缘有明显波浪。它生长缓慢，适应弱光，适合固定在沉木或石材上。种入底床时不要埋住根茎，以免腐烂。",
    "Anubias barteri var. nana ’Pinto’": "平托小榕是水榕的斑叶栽培品种，叶片长约 3-6 厘米，带有白色、浅绿色和深绿色斑纹；斑纹会随环境变化，有时也会长出全绿叶。适当提高光照可使白斑更明显，但光照过强容易损伤叶片并诱发藻类。它生长缓慢，适合固定在石材或沉木上，根茎不能埋入底床。",
    "Bacopa salzmannii 'Purple'": "紫虎耳原产南美洲湿地，叶片呈紫色和绿色。中高强度光照更有利于紫色发色，适合放在中景或后景。富含养分的底床、定期施肥和补充 CO₂ 有助于维持生长与色彩。生长速度中等，可通过茎段扦插繁殖。",
    "Bacopa monnieri 'Compact'": "迷你小对叶是 Bacopa monnieri 的紧凑型栽培品种，光照良好时株型接近匍匐。剪去向上直立生长的枝条，可促使它长出更多侧枝，保持低矮紧凑；它在其他水草的阴影下也能生长。适合用作稍高的铺地草，或种在中景、前景。不补充 CO₂ 或光照较弱时，植株会更直立，株型也会变得松散。",
    "Bucephalandra sordidula 'Blue'": "蓝色辣椒榕原产婆罗洲河岸，叶片在光线下会呈现蓝色光泽。它生长缓慢，养护要求不高，低到中等光照即可生长；较强光照可让色泽更明显。适合固定在沉木或石材上，用作前景或中景。",
    "Hygrophila odora": "香水蓑衣生长较快，叶片鲜绿，容易形成浓密株丛，适合中景或后景。它对水质和光照的适应范围较广，中等光照即可正常生长。定期修剪可保持紧凑株型，新鲜绿色也能与红色或深色水草形成对比。",
    "Hygrophila polysperma 'White'": "白青叶是在丹麦 Tropica 温室选育的品种。水上叶为浅绿色，有时带有细小突起；转为水下生长后，叶片会呈现浅绿色和白色斑纹。它直立生长、容易分枝，定期修剪可使株型更紧凑。生长速度较慢，适应范围较广；充足光照能让白斑更清楚，但仍需避免过强光照。适合中景或后景。",
    "Hygrophila serpyllum": "匍匐水蓑衣株型低矮紧凑，叶片鲜绿，可用于前景或中景，并逐渐铺展成草坪。它在中等光照下生长良好，对水质的适应范围较广，生长速度容易控制。偶尔修剪即可维持低矮、浓密的状态。",
    "Eleocharis pusilla 'Mini'": "迷你牛毛毡采用密封杯组织培养。它的株型比常见的迷你牛毛毡更低矮，由美国水草玩家 Thomas Barr 提供给 Tropica。将植株分成小丛并分散栽种，短时间内即可形成致密草坪。充足光照有助于维持低矮株型；叶片仅长约 3-5 厘米，日常修剪较少，适合迷你水族箱。",
    "Microsorum pteropus nano wood": "这款产品将细叶铁皇冠预先固定在迷你沉木上，可直接放入水族箱。细长拱形的叶片从沉木上展开，适合小型造景。它在低到中等光照下即可生长，无需额外补充 CO₂，生长缓慢，日常养护和修剪都很少。",
    "Riccardia chamedryfolia": "珊瑚莫丝属于叶苔类，枝体细密，外形近似珊瑚，适合固定在石材或沉木上，也可铺成低矮草坪。它适应低到中等光照和多种水质，生长缓慢，修剪需求较少，能够形成紧密的小丛。",
    "Sagittaria subulata 'Needle Leaf'": "针叶水兰可能是迷你水兰的一个变种，叶片狭长，长约 15-30 厘米，宽仅数毫米。它容易养护，中等光照下即可生长，无需额外补充 CO₂；强光下叶片可能略带橙色。植株直立，适合作为自然风格的后景草，并可通过走茎繁殖。",
    "Selaginella uncinata": "翠云草是一种匍匐生长的卷柏类植物，茎叶密集，叶片带有蓝绿色光泽，适合潮湿的雨林缸或沼泽缸。它可以覆盖底床和造景素材，成活后生长较快，也可能蔓延到邻近植物上，可通过定期修剪控制范围。",
    "Solenostoma tetragonum 'Pearl Moss'": "珍珠莫丝是产自婆罗洲的叶苔类植物。小而圆的半透明叶片会形成深绿色、垫状的紧密株丛。它生长缓慢，可自然附着在石材和沉木上，适合迷你水族箱或大型造景中的细节位置，也可与辣椒榕等耐阴水草搭配。稳定的环境、均衡施肥和补充 CO₂ 有利于生长；状态良好时，密集叶片间会出现珍珠状氧气泡。",
    "Spirodela polyrrhiza": "紫萍是漂浮在水面的浮水植物，小而圆的绿色叶状体可为鱼类遮阴并提供躲藏处。它在低到中等光照下都能快速生长，通过吸收水中养分抑制藻类并改善水质。需要定期捞除过密植株，避免遮挡下层水草的光照。",
}

INTRODUCTION_OVERRIDES_BY_PRODUCT_CODE = {
    "000C ST": "Cladophora aegagropila 并不是真正的水草，而是直径约 3-10 厘米的球状藻体。水波推动会使它逐渐形成球形；放入水族箱后需定期翻面，才能保持形状。它也可以分成小块，之后重新长成球状，或固定在沉木和石材上铺展开来。日本部分地区对其实施保护。",
    "000D MP": "本产品包含 3 个采用透气吸塑包装的海藻球。Cladophora aegagropila 并不是真正的水草，而是直径约 3-10 厘米的球状藻体。水波推动会使它逐渐形成球形；放入水族箱后需定期翻面，才能保持形状。它也可以分成小块，之后重新长成球状，或固定在沉木和石材上铺展开来。日本部分地区对其实施保护。",
    "000E POR": "Cladophora aegagropila 并不是真正的水草，而是直径约 2-10 厘米的球状藻体。水波推动会使它逐渐形成球形；放入水族箱后需定期翻面，才能保持形状。它也可以分成小块，之后重新长成球状，或固定在沉木和石材上铺展开来。日本部分地区对其实施保护。",
}

TEXT_REPLACEMENTS = (
    ("活的水草放在盆里，装在透气的吸塑包装里走。", "盆栽水草，采用透气吸塑包装。"),
    ("盆栽的活水草，装在透气的泡罩包装中带走。", "盆栽水草，采用透气吸塑包装。"),
    ("闭杯组织培养的水族植物", "采用密封杯组织培养的水草"),
    ("闭杯组织培养的水草", "采用密封杯组织培养的水草"),
    ("水族馆植物", "水草"),
    ("水族植物", "水草"),
    ("水生植物", "水草"),
    ("水族馆", "水族箱"),
    ("坦克", "水族箱"),
    ("水箱", "水族箱"),
    ("前景植物", "前景草"),
    ("中景植物", "中景草"),
    ("背景植物", "后景草"),
    ("地被植物", "铺地草"),
    ("岩石和木材", "石材和沉木"),
    ("岩石或木材", "石材或沉木"),
    ("木材和岩石", "沉木和石材"),
    ("木材或岩石", "沉木或石材"),
    ("岩石和木头", "石材和沉木"),
    ("岩石或木头", "石材或沉木"),
    ("木头和岩石", "沉木和石材"),
    ("木头或岩石", "沉木或石材"),
    ("根和石头", "沉木和石材"),
    ("根和岩石", "沉木和石材"),
    ("石头和树根", "石材和沉木"),
    ("岩石和树根", "石材和沉木"),
    ("石头", "石材"),
    ("岩石", "石材"),
    ("木头", "沉木"),
    ("木材", "沉木"),
    ("浮木", "沉木"),
    ("树根", "沉木"),
    ("基质", "底床"),
    ("纳米水族箱", "迷你水族箱"),
    ("纳米水箱", "迷你水族箱"),
    ("苔藓", "莫丝"),
    ("地毯", "草坪"),
    ("跑步者", "走茎"),
    ("流纹", "走茎"),
    ("每个玫瑰花", "每个莲座丛"),
    ("玫瑰花状", "莲座状"),
    ("玫瑰状", "莲座状"),
    ("砍伐", "修剪"),
    ("工厂", "水草"),
    ("发酵剂植物", "入门水草"),
    ("茎植物", "有茎草"),
    ("培养形式", "栽培品种"),
    ("锚上", "配重环中"),
    ("取下锚", "取下配重环"),
    ("一束茎或幼苗聚集在配重环中。", "成束茎草或幼苗由配重环固定。"),
    ("取下配重环并分裂成单独的植物。", "取下配重环，将植株逐一分开。"),
    ("根很快就会发育，植物开始生长。", "植株很快会长出新根并恢复生长。"),
    ("底部底床", "底床"),
    ("种植在底部", "种入底床"),
    ("重新种植在底部", "重新种入底床"),
    ("蔓延到底部", "沿底床蔓延"),
    ("营养丰富的底部", "富含养分的底床"),
    ("底层", "底床"),
    ("营养物质", "养分"),
    ("营养素", "养分"),
    ("水参数", "水质参数"),
    ("水族造景师", "造景玩家"),
    ("水族爱好者", "水草玩家"),
    ("水生花园", "水草造景"),
    ("水生天堂", "水草造景"),
    ("低维护", "养护省心"),
    ("有吸引力的", "观赏性较好的"),
    ("美观、致密的外观", "紧凑浓密的株型"),
    ("紧凑且有吸引力的生长", "紧凑的株型"),
    ("紧凑且有吸引力的增长", "紧凑的株型"),
    ("低矮且紧密的生长", "低矮紧凑的株型"),
    ("生长速度一般为平均", "生长速度中等"),
    ("增长率是平均水平", "生长速度中等"),
    ("隐花藻", "椒草"),
    ("匍匐茎、根茎", "匍匐根茎"),
    ("印度美女", "这种水草"),
    ("完美搭配", "搭配效果较好"),
    ("随意彻底修剪一组植物", "可对成丛植株进行重剪"),
    ("并且你的植物会变得更厚", "使株丛更加浓密"),
    ("光照条件的减少", "光照较弱"),
    ("植物会变得更加垂直生长并且不那么紧凑", "植株会更直立，株型也会变得松散"),
    ("稍高一点的草坪", "稍高的铺地草"),
    ("水族箱中部或前面", "水族箱中景或前景"),
    ("制作草坪", "形成草坪"),
    ("发挥最佳性能", "达到最佳状态"),
    ("茁壮成长", "生长良好"),
    ("整体外观", "整体状态"),
    ("主要优点", "主要特点："),
    ("爪哇蕨", "铁皇冠"),
    ("爪哇苔藓", "爪哇莫丝"),
    ("圣诞苔藓", "圣诞莫丝"),
    ("台湾苔藓", "台湾莫丝"),
    ("垂枝苔藓", "垂泪莫丝"),
    ("二氧化碳", "CO₂"),
    ("光强度", "光照强度"),
    ("没有CO₂添加", "未添加 CO₂"),
    ("添加CO₂", "添加 CO₂"),
    ("特别适合", "适合"),
    ("非常适合", "适合"),
    ("完美适合", "适合"),
    ("绝佳选择", "合适的选择"),
    ("理想选择", "合适的选择"),
    ("最为美丽", "观赏效果最好"),
    ("极其美丽的", "观赏性较强的"),
    ("非常美丽的", "观赏性较强的"),
    ("美丽的", ""),
    ("漂亮且", ""),
    ("脱颖而出", "较为醒目"),
    ("令人惊叹的", "观赏性很强的"),
    ("迷人的", "颇具观赏性的"),
    ("充满活力的", "鲜艳的"),
    ("自愿分枝", "容易分枝"),
    ("自愿形成", "容易形成"),
    ("愿意产生", "容易长出"),
)


def atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def parse_translation_payload(payload: object) -> str:
    if isinstance(payload, list) and payload and isinstance(payload[0], str):
        return payload[0]
    if isinstance(payload, list) and payload and isinstance(payload[0], list):
        return "".join(
            part[0]
            for part in payload[0]
            if isinstance(part, list) and part and isinstance(part[0], str)
        )
    raise ValueError(f"unexpected translation response: {payload!r}")


def placeholder(index: int) -> str:
    """Return visually distinct letter-only tokens that translators preserve."""
    letters = ""
    value = index
    while True:
        value, remainder = divmod(value, 26)
        letters = chr(ord("A") + remainder) + letters
        if value == 0:
            break
        value -= 1
    return f"ZXQKEEP{letters}QXZ"


def protect_terms(
    text: str,
    phrase_translations: dict[str, str],
    name_translations: dict[str, list[str]],
    genera: set[str],
) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}

    for name in sorted(name_translations, key=len, reverse=True):
        if name in text:
            token = placeholder(len(replacements))
            text = text.replace(name, token)
            replacements[token] = name_translations[name][0]

    matched_phrases = [
        phrase
        for phrase in sorted(phrase_translations, key=len, reverse=True)
        if phrase in text
    ]
    for phrase in matched_phrases:
        token = placeholder(len(replacements))
        text = text.replace(phrase, token)
        replacements[token] = phrase_translations[phrase]

    for genus in sorted(genera, key=len, reverse=True):
        if re.search(rf"\b{re.escape(genus)}\b", text):
            token = placeholder(len(replacements))
            text = re.sub(rf"\b{re.escape(genus)}\b", token, text)
            replacements[token] = genus
    return text, replacements


def request_translation(text: str) -> str:
    endpoints = (
        (
            "https://clients5.google.com/translate_a/t",
            {"client": "dict-chrome-ex", "sl": "en", "tl": "zh-CN", "q": text},
        ),
        (
            "https://translate.googleapis.com/translate_a/single",
            {
                "client": "dict-chrome-ex",
                "sl": "en",
                "tl": "zh-CN",
                "dt": "t",
                "q": text,
            },
        ),
    )
    last_error: Exception | None = None
    for attempt in range(4):
        for endpoint, params in endpoints:
            url = endpoint + "?" + urllib.parse.urlencode(params)
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                return parse_translation_payload(payload)
            except Exception as error:
                last_error = error
        if attempt < 3:
            time.sleep(1.5 * (2**attempt))
    raise RuntimeError(f"translation failed: {last_error}")


def translate_introduction(
    source: str,
    phrase_translations: dict[str, str],
    name_translations: dict[str, list[str]],
    genera: set[str],
) -> str:
    if not source:
        return ""
    protected, replacements = protect_terms(
        source, phrase_translations, name_translations, genera
    )
    translated = request_translation(protected)
    translated = re.sub(r"[\u200b-\u200d\ufeff]", "", translated)
    for token, replacement in replacements.items():
        if token not in translated:
            raise ValueError(f"translation lost protected token {token}")
        translated = translated.replace(token, replacement)
    return translated


def build_translation_cache(
    introductions: list[str],
    phrase_translations: dict[str, str],
    name_translations: dict[str, list[str]],
    genera: set[str],
    workers: int,
    refresh: bool,
) -> dict[str, str]:
    if TRANSLATION_CACHE_PATH.exists() and not refresh:
        cache = json.loads(TRANSLATION_CACHE_PATH.read_text(encoding="utf-8"))
    else:
        cache = {}
    cache[""] = ""
    missing = [text for text in introductions if text not in cache]

    for offset in range(0, len(missing), workers):
        batch = missing[offset : offset + workers]
        failures: list[str] = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    translate_introduction,
                    text,
                    phrase_translations,
                    name_translations,
                    genera,
                ): text
                for text in batch
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    cache[source] = future.result()
                except Exception as error:
                    failures.append(f"{source[:80]!r}: {error}")
        atomic_write_json(TRANSLATION_CACHE_PATH, cache)
        completed = min(offset + len(batch), len(missing))
        if completed % 25 == 0 or completed == len(missing):
            print(f"translated {completed}/{len(missing)} introductions")
        if failures:
            raise RuntimeError("translation failures:\n" + "\n".join(failures))
        time.sleep(0.25)
    return cache


def naturalize_translation(
    translated: str,
    name_translations: dict[str, list[str]],
    name: str,
    product_code: str,
) -> str:
    if product_code in INTRODUCTION_OVERRIDES_BY_PRODUCT_CODE:
        return INTRODUCTION_OVERRIDES_BY_PRODUCT_CODE[product_code]
    if name in INTRODUCTION_OVERRIDES_BY_NAME:
        return INTRODUCTION_OVERRIDES_BY_NAME[name]

    text = translated
    for name in sorted(name_translations, key=len, reverse=True):
        text = text.replace(name, name_translations[name][0])
    for genus, chinese in GENUS_CN.items():
        text = text.replace(genus, chinese)
    for old, new in TEXT_REPLACEMENTS:
        text = text.replace(old, new)

    text = text.replace("CO2", "CO₂").replace("CO 2", "CO₂")
    text = text.replace("0,5", "0.5")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"\s+([，。；：！？、）】])", r"\1", text)
    text = re.sub(r"([，。；：！？、])\s+", r"\1", text)
    text = re.sub(r"([（【])\s+", r"\1", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*(?:至|到)\s*(\d+(?:\.\d+)?)\s*厘米", r"\1-\2 厘米", text)
    text = re.sub(r"(?<=\d)\s*(厘米|毫米|米|升|毫克)", r" \1", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])(?=[A-Za-z])", " ", text)
    text = re.sub(r"(?<=[A-Za-z])(?=[\u4e00-\u9fff])", " ", text)
    text = re.sub(r"(\d+)“", r"\1 英寸", text)
    text = text.replace(" - ", "，")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--refresh-translations", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 5:
        parser.error("--workers must be between 1 and 5")

    raw_payload = json.loads(RAW_DETAIL_PATH.read_text(encoding="utf-8"))
    formatted_list = json.loads(FORMATTED_LIST_PATH.read_text(encoding="utf-8"))["list"]
    raw_details = raw_payload["detail_list"]

    formatted_by_key = {
        (item["name"], item["product_code"]): item for item in formatted_list
    }
    detail_keys = {(item["name"], item["product_code"]) for item in raw_details}
    if detail_keys != set(formatted_by_key):
        missing = sorted(detail_keys - set(formatted_by_key))
        extra = sorted(set(formatted_by_key) - detail_keys)
        raise ValueError(f"plant list mismatch; missing={missing}, extra={extra}")

    name_translations: dict[str, list[str]] = {}
    phrase_translations: dict[str, str] = {}
    for item in formatted_list:
        name_translations.setdefault(item["name"], item["name_cns"])
        phrase_translations.update(zip(item["descriptions"], item["descriptions_cn"]))
    genera = {item["name"].split()[0] for item in raw_details}
    introductions = list(dict.fromkeys(item["introduction"] for item in raw_details))
    translations = build_translation_cache(
        introductions,
        phrase_translations,
        name_translations,
        genera,
        workers=args.workers,
        refresh=args.refresh_translations,
    )

    formatted_details = []
    for detail in raw_details:
        list_item = formatted_by_key[(detail["name"], detail["product_code"])]
        properties = dict(detail["properties"])
        origin = properties["origin"]
        if origin not in ORIGIN_CN:
            raise ValueError(f"unknown origin {origin!r}")
        properties["type_cn"] = list_item["type_cn"]
        properties["origin_cn"] = ORIGIN_CN[origin]
        formatted_details.append(
            {
                "name": detail["name"],
                "name_cns": list_item["name_cns"],
                "product_code": detail["product_code"],
                "properties": properties,
                "introduction": detail["introduction"],
                "introduction_cn": naturalize_translation(
                    translations[detail["introduction"]],
                    name_translations,
                    detail["name"],
                    detail["product_code"],
                ),
                "illustration": detail["illustration"],
                "images": detail["images"],
                "layouts": detail["layouts"],
            }
        )

    payload = {
        "detail_list": formatted_details,
        "meta": {
            "property_description": raw_payload["meta"]["property_description"],
            "property_description_cn": PROPERTY_DESCRIPTION_CN,
        },
    }
    atomic_write_json(OUTPUT_PATH, payload)
    print(f"wrote {len(formatted_details)} translated details to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
