#!/usr/bin/env python3
"""Scrape the current Tropica plant list into a JSON file.

The page is server-rendered, so this script intentionally uses only Python's
standard library: urllib for HTTP and HTMLParser for extracting list items.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


DEFAULT_URL: Final = "https://tropica.com/en/plants/"
DEFAULT_OUTPUT: Final = "raw/tropica.com/plant-list.json"
ITEM_CODE_RE: Final = re.compile(
    r"\(\s*Item\s+no\.\s*(?P<code>.*?)\s*\)", re.IGNORECASE | re.DOTALL
)
WHITESPACE_RE: Final = re.compile(r"\s+")


def clean_text(value: str) -> str:
    """Collapse HTML formatting whitespace into a single space."""
    return WHITESPACE_RE.sub(" ", value).strip()


@dataclass
class PlantListItem:
    name: str
    type: str
    product_code: str
    descriptions: list[str]
    cover: str
    detail_path: str


class TropicaPlantParser(HTMLParser):
    """Extract plant rows from Tropica's server-rendered list page."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.items: list[PlantListItem] = []
        self.div_depth = 0
        self.item_root_depth: int | None = None
        self.name_area_depth: int | None = None
        self.in_name_strong = False
        self.description_parts: list[str] | None = None
        self.current: dict[str, object] | None = None

    @staticmethod
    def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
        values = dict(attrs).get("class") or ""
        return set(values.split())

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)

        if tag == "div":
            self.div_depth += 1
            classes = self._classes(attrs)

            if self.current is None and "plant-item" in classes:
                self.current = {
                    "href": "",
                    "cover": "",
                    "name_parts": [],
                    "meta_parts": [],
                    "descriptions": [],
                }
                self.item_root_depth = self.div_depth

            if self.current is not None and "plantGallaryItemName" in classes:
                self.name_area_depth = self.div_depth

        if self.current is None:
            return

        if tag == "a" and not self.current["href"]:
            self.current["href"] = attributes.get("href") or ""
        elif tag == "img" and not self.current["cover"]:
            self.current["cover"] = attributes.get("src") or ""
        elif tag == "strong" and self.name_area_depth is not None:
            self.in_name_strong = True
        elif tag == "li":
            self.description_parts = []

    def handle_data(self, data: str) -> None:
        if self.current is None:
            return

        if self.description_parts is not None:
            self.description_parts.append(data)

        if self.name_area_depth is not None:
            key = "name_parts" if self.in_name_strong else "meta_parts"
            parts = self.current[key]
            assert isinstance(parts, list)
            parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.current is not None:
            if tag == "strong" and self.in_name_strong:
                self.in_name_strong = False
            elif tag == "li" and self.description_parts is not None:
                description = clean_text("".join(self.description_parts))
                descriptions = self.current["descriptions"]
                assert isinstance(descriptions, list)
                if description:
                    descriptions.append(description)
                self.description_parts = None

            if tag == "div" and self.name_area_depth == self.div_depth:
                self.name_area_depth = None

            if tag == "div" and self.item_root_depth == self.div_depth:
                self._finish_item()

        if tag == "div":
            self.div_depth -= 1

    def _finish_item(self) -> None:
        assert self.current is not None

        name = clean_text("".join(self.current["name_parts"]))
        meta = clean_text(" ".join(self.current["meta_parts"]))
        code_match = ITEM_CODE_RE.search(meta)
        product_code = clean_text(code_match.group("code")) if code_match else ""
        plant_type = clean_text(ITEM_CODE_RE.sub(" ", meta))
        href = str(self.current["href"])
        cover = str(self.current["cover"])
        descriptions = self.current["descriptions"]
        assert isinstance(descriptions, list)

        # Ignore unrelated or malformed markup instead of emitting partial rows.
        if name and href:
            self.items.append(
                PlantListItem(
                    name=name,
                    type=plant_type,
                    product_code=product_code,
                    descriptions=descriptions,
                    cover=urljoin(self.base_url, cover) if cover else "",
                    detail_path=urlsplit(urljoin(self.base_url, href)).path,
                )
            )

        self.current = None
        self.item_root_depth = None
        self.name_area_depth = None
        self.in_name_strong = False
        self.description_parts = None


def fetch_html(url: str, timeout: float, retries: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; TropicaPlantListScraper/1.0; "
                "+https://tropica.com/)"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError) as exc:
            if attempt >= retries:
                raise RuntimeError(f"Failed to download {url}: {exc}") from exc
            time.sleep(2**attempt)

    raise AssertionError("unreachable")


def scrape(url: str, timeout: float, retries: int) -> list[PlantListItem]:
    parser = TropicaPlantParser(url)
    parser.feed(fetch_html(url, timeout=timeout, retries=retries))
    parser.close()
    return parser.items


def validate(items: list[PlantListItem]) -> None:
    if not items:
        raise RuntimeError("No plant items were found; the page structure may have changed")

    missing_required = [
        index
        for index, item in enumerate(items)
        if not item.name or not item.product_code or not item.detail_path
    ]
    if missing_required:
        preview = ", ".join(map(str, missing_required[:10]))
        raise RuntimeError(f"Required fields are missing in item indexes: {preview}")

    detail_paths = [item.detail_path for item in items]
    if len(detail_paths) != len(set(detail_paths)):
        raise RuntimeError("Duplicate detail_path values were found")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="Plant list page URL")
    parser.add_argument(
        "-o", "--output", type=Path, default=Path(DEFAULT_OUTPUT), help="JSON path"
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout")
    parser.add_argument("--retries", type=int, default=2, help="HTTP retry count")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        items = scrape(args.url, timeout=args.timeout, retries=args.retries)
        validate(items)
        payload = {"list": [asdict(item) for item in items]}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {len(items)} plants to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
