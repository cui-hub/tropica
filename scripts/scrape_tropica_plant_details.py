#!/usr/bin/env python3
"""Scrape Tropica plant detail pages into the raw detail-list JSON schema."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, urlopen


ROOT: Final = Path(__file__).resolve().parents[1]
BASE_URL: Final = "https://tropica.com/"
DEFAULT_INPUT: Final = ROOT / "raw" / "tropica.com" / "plant-list.json"
DEFAULT_OUTPUT: Final = ROOT / "raw" / "tropica.com" / "plant-detail-list.json"
PROPERTY_KEYS: Final = (
    "type",
    "origin",
    "growth_rate",
    "height",
    "light_requirement",
    "co2_requirement",
)
LABEL_TO_PROPERTY: Final = {
    "type": "type",
    "origin": "origin",
    "growth rate": "growth_rate",
    "height": "height",
    "light demand": "light_requirement",
    "co2": "co2_requirement",
}
HELP_ID_TO_PROPERTY: Final = {
    "plant-spec-help-origin": "origin",
    "plant-spec-help-growthrate": "growth_rate",
    "plant-spec-help-height": "height",
    "plant-spec-help-light": "light_requirement",
    "plant-spec-help-co2": "co2_requirement",
}
WHITESPACE_RE: Final = re.compile(r"\s+")


def clean_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def encoded_url(url: str) -> str:
    """Encode spaces and Unicode while preserving URL separators."""
    return quote(url, safe=":/?&=%+#[]!$'()*;,")


@dataclass
class PlantDetailProperty:
    type: str
    origin: str
    growth_rate: str
    height: str
    light_requirement: str
    co2_requirement: str


@dataclass
class PlantDetailItem:
    name: str
    product_code: str
    properties: PlantDetailProperty
    introduction: str
    illustration: str
    images: list[str]
    layouts: list[str]


class TropicaPlantDetailParser(HTMLParser):
    """Extract one plant detail page using Tropica's semantic CSS classes."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.div_depth = 0
        self.plant_root_depth: int | None = None
        self.main_image_depth: int | None = None
        self.thumbs_depth: int | None = None
        self.related_layouts_depth: int | None = None
        self.layout_item_depth: int | None = None
        self.layout_title_depth: int | None = None
        self.right_pane_depth: int | None = None
        self.description_depth: int | None = None
        self.illustration_area_depth: int | None = None
        self.in_title = False
        self.in_specification_table = False
        self.current_cell: str | None = None
        self.current_cell_parts: list[str] = []
        self.current_row: dict[str, object] | None = None

        self.title_parts: list[str] = []
        self.introduction_parts: list[str] = []
        self.layout_title_parts: list[str] = []
        self.images: list[str] = []
        self.layouts: list[str] = []
        self.illustration = ""
        self.properties = {key: "" for key in PROPERTY_KEYS}
        self.property_descriptions = {key: "" for key in PROPERTY_KEYS}

    @staticmethod
    def classes(attrs: list[tuple[str, str | None]]) -> set[str]:
        return set((dict(attrs).get("class") or "").split())

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        classes = self.classes(attrs)

        if tag == "div":
            self.div_depth += 1
            if "plant-details" in classes:
                self.plant_root_depth = self.div_depth
            if self.plant_root_depth is not None:
                if "mainimage" in classes:
                    self.main_image_depth = self.div_depth
                if "thumbs" in classes:
                    self.thumbs_depth = self.div_depth
                if "relatedlayouts" in classes:
                    self.related_layouts_depth = self.div_depth
                if (
                    self.related_layouts_depth is not None
                    and "layout-item" in classes
                ):
                    self.layout_item_depth = self.div_depth
                if self.layout_item_depth is not None and "title" in classes:
                    self.layout_title_depth = self.div_depth
                    self.layout_title_parts = []
                if "rightpane" in classes:
                    self.right_pane_depth = self.div_depth
                if self.right_pane_depth is not None and "description" in classes:
                    self.description_depth = self.div_depth
                if self.right_pane_depth is not None and "text-center" in classes:
                    self.illustration_area_depth = self.div_depth

        if self.plant_root_depth is None:
            return

        if tag == "h1":
            self.in_title = True
        elif tag == "a":
            href = attributes.get("href") or ""
            if href and (
                self.main_image_depth is not None or self.thumbs_depth is not None
            ):
                image = urljoin(self.base_url, href)
                is_tropica_image = urlsplit(image).path.lower().endswith(
                    "/imagegen.ashx"
                )
                if is_tropica_image and image not in self.images:
                    self.images.append(image)
            elif href and self.illustration_area_depth is not None:
                self.illustration = urljoin(self.base_url, href)
        elif tag == "table" and "specficationTable" in classes:
            self.in_specification_table = True
        elif tag == "tr" and self.in_specification_table:
            self.current_row = {
                "is_help": "plantInfoHelpText" in classes,
                "id": attributes.get("id") or "",
                "header": "",
                "cells": [],
            }
        elif (
            tag in {"th", "td"}
            and self.in_specification_table
            and self.current_row is not None
        ):
            self.current_cell = tag
            self.current_cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.plant_root_depth is None:
            return
        if self.in_title:
            self.title_parts.append(data)
        if self.description_depth is not None:
            self.introduction_parts.append(data)
        if self.layout_title_depth is not None:
            self.layout_title_parts.append(data)
        if self.current_cell is not None:
            self.current_cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.plant_root_depth is not None:
            if tag == "h1":
                self.in_title = False
            elif tag in {"th", "td"} and self.current_cell is not None:
                self._finish_cell()
            elif tag == "tr" and self.current_row is not None:
                self._finish_row()
            elif tag == "table" and self.in_specification_table:
                self.in_specification_table = False

            if tag == "div":
                if self.layout_title_depth == self.div_depth:
                    title = clean_text(" ".join(self.layout_title_parts))
                    if title and title not in self.layouts:
                        self.layouts.append(title)
                    self.layout_title_depth = None
                    self.layout_title_parts = []
                if self.layout_item_depth == self.div_depth:
                    self.layout_item_depth = None
                if self.related_layouts_depth == self.div_depth:
                    self.related_layouts_depth = None
                if self.main_image_depth == self.div_depth:
                    self.main_image_depth = None
                if self.thumbs_depth == self.div_depth:
                    self.thumbs_depth = None
                if self.description_depth == self.div_depth:
                    self.description_depth = None
                if self.illustration_area_depth == self.div_depth:
                    self.illustration_area_depth = None
                if self.right_pane_depth == self.div_depth:
                    self.right_pane_depth = None
                if self.plant_root_depth == self.div_depth:
                    self.plant_root_depth = None

        if tag == "div":
            self.div_depth -= 1

    def _finish_cell(self) -> None:
        assert self.current_row is not None
        value = clean_text(" ".join(self.current_cell_parts))
        if self.current_cell == "th":
            self.current_row["header"] = value
        else:
            cells = self.current_row["cells"]
            assert isinstance(cells, list)
            cells.append(value)
        self.current_cell = None
        self.current_cell_parts = []

    def _finish_row(self) -> None:
        assert self.current_row is not None
        cells = self.current_row["cells"]
        assert isinstance(cells, list)
        if self.current_row["is_help"]:
            key = HELP_ID_TO_PROPERTY.get(str(self.current_row["id"]))
            if key and cells:
                self.property_descriptions[key] = cells[0]
        else:
            label = clean_text(str(self.current_row["header"])).rstrip(":")
            normalized_label = re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()
            key = LABEL_TO_PROPERTY.get(normalized_label)
            if key and cells:
                self.properties[key] = cells[0]
        self.current_row = None

    @property
    def title(self) -> str:
        return clean_text(" ".join(self.title_parts))

    @property
    def introduction(self) -> str:
        return clean_text(" ".join(self.introduction_parts))


def fetch_html(url: str, timeout: float, retries: int) -> str:
    request = Request(
        encoded_url(url),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; TropicaPlantDetailScraper/1.0; "
                "+https://tropica.com/)"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"failed to download {url}: {last_error}")


def scrape_item(
    source_item: dict, timeout: float, retries: int
) -> tuple[PlantDetailItem, dict[str, str]]:
    url = urljoin(BASE_URL, source_item["detail_path"])
    parser = TropicaPlantDetailParser(BASE_URL)
    parser.feed(fetch_html(url, timeout=timeout, retries=retries))
    parser.close()

    source_name = clean_text(source_item["name"])
    if parser.title != source_name:
        raise ValueError(
            f"title mismatch for {url}: list={source_name!r}, detail={parser.title!r}"
        )
    if not parser.images:
        raise ValueError(f"missing detail images on {url}")

    detail = PlantDetailItem(
        name=source_item["name"],
        product_code=source_item["product_code"],
        properties=PlantDetailProperty(**parser.properties),
        introduction=parser.introduction,
        illustration=parser.illustration,
        images=parser.images,
        layouts=parser.layouts,
    )
    return detail, parser.property_descriptions


def merge_property_descriptions(
    descriptions: list[dict[str, str]],
) -> dict[str, str]:
    merged: dict[str, str] = {}
    for key in PROPERTY_KEYS:
        values = {description[key] for description in descriptions if description[key]}
        if len(values) > 1:
            raise ValueError(
                f"inconsistent property descriptions for {key}: {sorted(values)}"
            )
        merged[key] = next(iter(values), "")
    return merged


def validate(details: list[PlantDetailItem], expected_count: int) -> None:
    if len(details) != expected_count:
        raise ValueError(f"expected {expected_count} details, got {len(details)}")
    keys = [(item.name, item.product_code) for item in details]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate name/product_code pairs in detail output")
    for index, item in enumerate(details):
        if len(item.images) != len(set(item.images)):
            raise ValueError(f"duplicate images in detail index {index}")
        if len(item.layouts) != len(set(item.layouts)):
            raise ValueError(f"duplicate layouts in detail index {index}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    return args


def main() -> int:
    args = parse_args()
    try:
        source_items = json.loads(args.input.read_text(encoding="utf-8"))["list"]
        results: dict[int, PlantDetailItem] = {}
        descriptions: list[dict[str, str]] = []
        failures: list[str] = []

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(scrape_item, item, args.timeout, args.retries): index
                for index, item in enumerate(source_items)
            }
            for completed, future in enumerate(as_completed(futures), 1):
                index = futures[future]
                try:
                    detail, property_descriptions = future.result()
                    results[index] = detail
                    descriptions.append(property_descriptions)
                except Exception as error:
                    item = source_items[index]
                    failures.append(
                        f"[{index}] {item['name']} ({item['product_code']}): {error}"
                    )
                if completed % 20 == 0 or completed == len(source_items):
                    print(f"processed {completed}/{len(source_items)} detail pages")

        if failures:
            raise RuntimeError("scrape failures:\n" + "\n".join(failures))

        details = [results[index] for index in range(len(source_items))]
        validate(details, len(source_items))
        payload = {
            "detail_list": [asdict(item) for item in details],
            "meta": {
                "property_description": merge_property_descriptions(descriptions)
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(args.output)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"wrote {len(details)} details to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
