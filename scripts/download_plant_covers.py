#!/usr/bin/env python3
"""Download Tropica plant covers and populate formatted local_cover paths."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "formatted" / "plant-list.json"
IMAGE_DIR = ROOT / "formatted" / "assets" / "images"
LOCAL_IMAGE_DIR = Path("formatted") / "assets" / "images"

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_stem(name: str, product_code: str) -> str:
    """Build a readable, portable filename from the requested item fields."""
    stem = unicodedata.normalize("NFC", f"{name}_{product_code}")
    stem = INVALID_FILENAME_CHARS.sub("_", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    if not stem:
        raise ValueError("name and product_code produced an empty filename")
    return stem


def encode_url(url: str) -> str:
    # Tropica emits URLs containing spaces. Browsers encode them automatically.
    return urllib.parse.quote(url, safe=":/?&=%+#[]!$'()*;,")


def source_extension(url: str) -> str:
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    image_path = query.get("image", [""])[0]
    suffix = Path(image_path).suffix.lower()
    return ".jpg" if suffix == ".jpeg" else suffix


def image_extension(data: bytes, content_type: str | None, url: str) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith(b"BM"):
        return ".bmp"

    content_type = (content_type or "").split(";", 1)[0].strip().lower()
    type_extensions = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
    }
    if content_type in type_extensions:
        return type_extensions[content_type]

    suffix = source_extension(url)
    if suffix in {".png", ".jpg", ".gif", ".webp", ".bmp"}:
        return suffix
    raise ValueError(f"response is not a recognised image: {url}")


def is_valid_image(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        data = path.read_bytes()[:16]
        image_extension(data, None, str(path))
    except (OSError, ValueError):
        return False
    return True


def existing_image(item: dict, stem: str) -> Path | None:
    local_cover = item.get("local_cover", "")
    if local_cover:
        candidate = Path(local_cover)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if is_valid_image(candidate):
            return candidate

    suffix = source_extension(item["cover"])
    if suffix:
        candidate = IMAGE_DIR / f"{stem}{suffix}"
        if is_valid_image(candidate):
            return candidate
    return None


def download(item: dict, stem: str, force: bool) -> Path:
    if not force:
        found = existing_image(item, stem)
        if found is not None:
            return found

    url = encode_url(item["cover"])
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; TropicaPlantArchiver/1.0)",
            "Referer": "https://tropica.com/en/plants/",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
                extension = image_extension(data, response.headers.get("Content-Type"), url)
            if not data:
                raise ValueError(f"empty image response: {url}")

            destination = IMAGE_DIR / f"{stem}{extension}"
            temporary = destination.with_name(
                f".{destination.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp"
            )
            temporary.write_bytes(data)
            temporary.replace(destination)
            return destination
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to download {item['cover']}: {last_error}")


def local_path(path: Path) -> str:
    return (LOCAL_IMAGE_DIR / path.name).as_posix()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")

    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    items = payload["list"]
    stems = [safe_stem(item["name"], item["product_code"]) for item in items]
    duplicates = sorted({stem for stem in stems if stems.count(stem) > 1})
    if duplicates:
        raise ValueError(f"duplicate image filenames: {duplicates}")

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[int, Path] = {}
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(download, item, stem, args.force): index
            for index, (item, stem) in enumerate(zip(items, stems))
        }
        for completed, future in enumerate(as_completed(futures), 1):
            index = futures[future]
            try:
                results[index] = future.result()
            except Exception as error:
                failures.append(f"[{index}] {items[index]['name']}: {error}")
            if completed % 20 == 0 or completed == len(items):
                print(f"processed {completed}/{len(items)} images")

    if failures:
        raise RuntimeError("download failures:\n" + "\n".join(failures))

    for index, item in enumerate(items):
        item["local_cover"] = local_path(results[index])
    JSON_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"updated {len(items)} local_cover values in {JSON_PATH}")


if __name__ == "__main__":
    main()
