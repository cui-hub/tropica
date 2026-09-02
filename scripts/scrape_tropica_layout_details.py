#!/usr/bin/env python3
"""Scrape all Tropica aquascape detail pages into the raw layout schema."""

from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Final
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen


ROOT: Final = Path(__file__).resolve().parents[1]
BASE_URL: Final = "https://tropica.com/"
INDEX_URL: Final = urljoin(BASE_URL, "en/inspiration/")
DEFAULT_OUTPUT: Final = ROOT / "raw" / "tropica.com" / "layout-detail-list.json"
DIFFICULTIES: Final = {"Easy", "Medium", "Advanced"}
TECHNIQUE_KEYS: Final = (
    "aquarium",
    "volume",
    "light",
    "substrate",
    "gravel",
    "decoration",
    "filter",
    "co2",
    "fertiliser_weekly",
    "maintenance_hours_per_week",
)
LABEL_TO_TECHNIQUE: Final = {
    "aquarium": "aquarium",
    "volume": "volume",
    "light": "light",
    "substrate": "substrate",
    "gravel": "gravel",
    "decoration": "decoration",
    "filter": "filter",
    "co2": "co2",
    "fertiliser (weekly)": "fertiliser_weekly",
    "maintenance (hours per week)": "maintenance_hours_per_week",
}
WHITESPACE_RE: Final = re.compile(r"\s+")
VOLUME_SUFFIX_RE: Final = re.compile(r"\s*\(\s*[\d.,]+\s*L\s*\)\s*$", re.I)
PLANT_TEXT_RE: Final = re.compile(
    r"^([^:]*):\s*(.+?)\s*\(\s*(\d+)\s*pcs?\.?\s*\)\s*$", re.I
)


def clean_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def encoded_url(url: str) -> str:
    return quote(url, safe=":/?&=%+#[]!$'()*;,")


def fetch_html(url: str) -> str:
    request = Request(
        encoded_url(url),
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; TropicaPlantArchiver/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def classes(attrs: list[tuple[str, str | None]]) -> set[str]:
    return set((dict(attrs).get("class") or "").split())


def image_query_path(url: str) -> str:
    query = parse_qs(urlsplit(url).query)
    for key, values in query.items():
        if key.lower() == "image" and values:
            return unquote(values[0])
    return unquote(urlsplit(url).path)


def layout_code_from_url(url: str) -> str:
    match = re.search(r"/Layouts/([^/]+)/", image_query_path(url), re.I)
    return match.group(1) if match else ""


def product_code_from_url(url: str) -> str:
    match = re.search(r"/Plants/([^/]+)/", image_query_path(url), re.I)
    return match.group(1) if match else ""


def split_designers(value: str) -> list[str]:
    value = re.sub(r"^by\s+", "", clean_text(value), flags=re.I)
    if not value:
        return []
    return [
        part
        for part in (
            clean_text(item)
            for item in re.split(r"\s*(?:,|&|\band\b)\s*", value, flags=re.I)
        )
        if part
    ]


@dataclass
class LayoutTechnique:
    aquarium: str
    volume: str
    light: str
    substrate: str
    gravel: str
    decoration: str
    filter: str
    co2: str
    fertiliser_weekly: str
    maintenance_hours_per_week: str


@dataclass
class LayoutPlantItem:
    position: str
    name: str
    product_code: str
    quantity: int


@dataclass
class LayoutDetailItem:
    layout_id: str
    layout_code: str
    detail_path: str
    name: str
    designers: list[str]
    difficulty: str
    technique: LayoutTechnique
    descriptions: list[str]
    images: list[str]
    planting_plan: str
    pdf: str
    plants: list[LayoutPlantItem]


class TropicaLayoutIndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.detail_paths: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag != "a":
            return
        href = (dict(attrs).get("href") or "").strip()
        if not re.match(r"^/en/inspiration/layout/[^/?#]+/\d+/?$", href, re.I):
            return
        if href not in self.detail_paths:
            self.detail_paths.append(href)


class TropicaLayoutDetailParser(HTMLParser):
    def __init__(self, detail_path: str) -> None:
        super().__init__(convert_charrefs=True)
        self.detail_path = detail_path
        self.div_depth = 0
        self.layout_name_depth: int | None = None
        self.difficulty_depth: int | None = None
        self.thumbnails_depth: int | None = None
        self.designer_depth: int | None = None
        self.description_depth: int | None = None
        self.printguide_depth: int | None = None
        self.productrelations_depth: int | None = None
        self.plant_item_depth: int | None = None
        self.in_title = False
        self.in_specification_table = False
        self.current_cell: str | None = None
        self.current_cell_parts: list[str] = []
        self.current_label = ""
        self.in_description_paragraph = False
        self.description_paragraph_parts: list[str] = []

        self.title_parts: list[str] = []
        self.designer_parts: list[str] = []
        self.description_all_parts: list[str] = []
        self.descriptions: list[str] = []
        self.images: list[str] = []
        self.planting_plans: list[str] = []
        self.pdf = ""
        self.difficulty = ""
        self.technique = {key: "" for key in TECHNIQUE_KEYS}
        self.plants: list[LayoutPlantItem] = []
        self.plant_text_parts: list[str] = []
        self.plant_image = ""
        self.parse_errors: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        element_classes = classes(attrs)

        if tag == "div":
            self.div_depth += 1
            if "layoutname" in element_classes:
                self.layout_name_depth = self.div_depth
            if "difficulty" in element_classes:
                self.difficulty_depth = self.div_depth
            if "thumbnails" in element_classes:
                self.thumbnails_depth = self.div_depth
            if "designer" in element_classes:
                self.designer_depth = self.div_depth
            if "description" in element_classes:
                self.description_depth = self.div_depth
            if "printguide" in element_classes:
                self.printguide_depth = self.div_depth
            if "productrelations" in element_classes:
                self.productrelations_depth = self.div_depth
            if (
                "plant-item" in element_classes
                and self.productrelations_depth is not None
            ):
                self.plant_item_depth = self.div_depth
                self.plant_text_parts = []
                self.plant_image = ""

        elif tag == "h1" and self.layout_name_depth is not None:
            self.in_title = True
        elif tag == "table" and "specficationTable" in element_classes:
            self.in_specification_table = True
        elif tag in {"th", "td"} and self.in_specification_table:
            self.current_cell = tag
            self.current_cell_parts = []
        elif tag == "p" and self.description_depth is not None:
            self.in_description_paragraph = True
            self.description_paragraph_parts = []
        elif tag == "br" and self.in_description_paragraph:
            self.description_paragraph_parts.append(" ")

        if tag == "a":
            href = (attributes.get("href") or "").strip()
            if href and "galleryImage" in element_classes:
                absolute = urljoin(BASE_URL, href)
                if absolute not in self.images:
                    self.images.append(absolute)
            if (
                href
                and self.thumbnails_depth is not None
                and "fancybox" in element_classes
            ):
                absolute = urljoin(BASE_URL, href)
                if absolute not in self.planting_plans:
                    self.planting_plans.append(absolute)
            if href and self.printguide_depth is not None and not self.pdf:
                self.pdf = urljoin(BASE_URL, href)

        if tag == "img":
            src = (attributes.get("src") or "").strip()
            if src and self.difficulty_depth is not None:
                match = re.search(r"icon_difficulty_([A-Za-z]+)\.png", src, re.I)
                if match:
                    self.difficulty = match.group(1).title()
            if src and self.plant_item_depth is not None and not self.plant_image:
                self.plant_image = urljoin(BASE_URL, src)

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.current_cell is not None:
            self.current_cell_parts.append(data)
        if self.designer_depth is not None:
            self.designer_parts.append(data)
        if self.description_depth is not None:
            self.description_all_parts.append(data)
            if self.in_description_paragraph:
                self.description_paragraph_parts.append(data)
        if self.plant_item_depth is not None:
            self.plant_text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self.in_title = False
        elif tag in {"th", "td"} and self.current_cell == tag:
            value = clean_text("".join(self.current_cell_parts)).rstrip(":")
            if tag == "th":
                self.current_label = value.lower()
            else:
                key = LABEL_TO_TECHNIQUE.get(self.current_label)
                if key:
                    self.technique[key] = value
            self.current_cell = None
            self.current_cell_parts = []
        elif tag == "table" and self.in_specification_table:
            self.in_specification_table = False
        elif tag == "p" and self.in_description_paragraph:
            paragraph = clean_text("".join(self.description_paragraph_parts))
            if paragraph:
                self.descriptions.append(paragraph)
            self.in_description_paragraph = False
            self.description_paragraph_parts = []

        if tag != "div":
            return

        if self.plant_item_depth == self.div_depth:
            self.finish_plant_item()
            self.plant_item_depth = None
        if self.layout_name_depth == self.div_depth:
            self.layout_name_depth = None
        if self.difficulty_depth == self.div_depth:
            self.difficulty_depth = None
        if self.thumbnails_depth == self.div_depth:
            self.thumbnails_depth = None
        if self.designer_depth == self.div_depth:
            self.designer_depth = None
        if self.description_depth == self.div_depth:
            if not self.descriptions:
                description = clean_text("".join(self.description_all_parts))
                if description:
                    self.descriptions.append(description)
            self.description_depth = None
        if self.printguide_depth == self.div_depth:
            self.printguide_depth = None
        if self.productrelations_depth == self.div_depth:
            self.productrelations_depth = None
        self.div_depth -= 1

    def finish_plant_item(self) -> None:
        value = clean_text("".join(self.plant_text_parts))
        match = PLANT_TEXT_RE.match(value)
        product_code = product_code_from_url(self.plant_image)
        if not match or not product_code:
            self.parse_errors.append(
                f"could not parse layout plant: text={value!r}, image={self.plant_image!r}"
            )
            return
        self.plants.append(
            LayoutPlantItem(
                position=clean_text(match.group(1)),
                name=clean_text(match.group(2)),
                product_code=product_code,
                quantity=int(match.group(3)),
            )
        )

    def build_item(self) -> LayoutDetailItem:
        if self.parse_errors:
            raise ValueError("; ".join(self.parse_errors))

        title = clean_text("".join(self.title_parts))
        name = VOLUME_SUFFIX_RE.sub("", title).strip()
        layout_id = self.detail_path.rstrip("/").rsplit("/", 1)[-1]
        layout_code = layout_code_from_url(self.images[0]) if self.images else ""
        item = LayoutDetailItem(
            layout_id=layout_id,
            layout_code=layout_code,
            detail_path=self.detail_path,
            name=name,
            designers=split_designers("".join(self.designer_parts)),
            difficulty=self.difficulty,
            technique=LayoutTechnique(**self.technique),
            descriptions=self.descriptions,
            images=self.images,
            planting_plan=self.planting_plans[0] if self.planting_plans else "",
            pdf=self.pdf,
            plants=self.plants,
        )
        validate_item(item)
        return item


def validate_item(item: LayoutDetailItem) -> None:
    required = {
        "layout_id": item.layout_id,
        "layout_code": item.layout_code,
        "detail_path": item.detail_path,
        "name": item.name,
        "difficulty": item.difficulty,
        "images": item.images,
        "pdf": item.pdf,
        "plants": item.plants,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    if item.difficulty not in DIFFICULTIES:
        raise ValueError(f"unexpected difficulty: {item.difficulty!r}")
    if len(item.planting_plan) == 0:
        return
    if not item.planting_plan.startswith(("http://", "https://")):
        raise ValueError(f"invalid planting plan URL: {item.planting_plan!r}")


def scrape_detail(detail_path: str) -> LayoutDetailItem:
    parser = TropicaLayoutDetailParser(detail_path)
    parser.feed(fetch_html(urljoin(BASE_URL, detail_path)))
    parser.close()
    return parser.build_item()


def validate_collection(items: list[LayoutDetailItem], expected_count: int) -> None:
    if len(items) != expected_count:
        raise ValueError(f"expected {expected_count} layouts, got {len(items)}")
    for field in ("layout_id", "layout_code", "detail_path"):
        values = [getattr(item, field) for item in items]
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            raise ValueError(f"duplicate {field} values: {duplicates}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")

    index_parser = TropicaLayoutIndexParser()
    index_parser.feed(fetch_html(INDEX_URL))
    index_parser.close()
    detail_paths = index_parser.detail_paths
    if not detail_paths:
        raise RuntimeError("no layout detail paths found on the inspiration page")
    print(f"found {len(detail_paths)} layout detail pages", flush=True)

    results: dict[int, LayoutDetailItem] = {}
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(scrape_detail, detail_path): index
            for index, detail_path in enumerate(detail_paths)
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            index = futures[future]
            try:
                results[index] = future.result()
            except Exception as error:
                failures.append(f"{detail_paths[index]}: {error}")
            if completed % 10 == 0 or completed == len(detail_paths):
                print(f"processed {completed}/{len(detail_paths)} layouts", flush=True)

    if failures:
        raise RuntimeError("layout scrape failures:\n" + "\n".join(failures))

    items = [results[index] for index in range(len(detail_paths))]
    validate_collection(items, len(detail_paths))
    payload = {"detail_list": [asdict(item) for item in items]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)

    print(f"wrote {len(items)} layouts to {args.output}")
    print(f"gallery images: {sum(len(item.images) for item in items)}")
    print(f"planting plans: {sum(bool(item.planting_plan) for item in items)}")
    print(f"plant relations: {sum(len(item.plants) for item in items)}")


if __name__ == "__main__":
    main()
