#!/usr/bin/env python3
"""Download Tropica detail and illustration images into formatted assets."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

try:
    from .download_plant_covers import (
        encode_url,
        image_extension,
        is_valid_image,
        safe_stem,
        source_extension,
    )
except ImportError:
    from download_plant_covers import (
        encode_url,
        image_extension,
        is_valid_image,
        safe_stem,
        source_extension,
    )


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "formatted" / "plant-detail-list.json"
IMAGE_DIR = ROOT / "formatted" / "assets" / "images"
KNOWN_EXTENSIONS = (".png", ".jpg", ".gif", ".webp", ".bmp")


@dataclass(frozen=True)
class ImageTask:
    url: str
    stem: str


def existing_image(task: ImageTask) -> Path | None:
    preferred_extension = source_extension(task.url)
    extensions = (preferred_extension,) if preferred_extension else KNOWN_EXTENSIONS
    for extension in extensions:
        candidate = IMAGE_DIR / f"{task.stem}{extension}"
        if is_valid_image(candidate):
            return candidate
    return None


def download(task: ImageTask, force: bool) -> Path:
    if not force:
        found = existing_image(task)
        if found is not None:
            return found

    url = encode_url(task.url)
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
                extension = image_extension(
                    data, response.headers.get("Content-Type"), url
                )
            if not data:
                raise ValueError(f"empty image response: {task.url}")

            destination = IMAGE_DIR / f"{task.stem}{extension}"
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
    raise RuntimeError(f"failed to download {task.url}: {last_error}")


def build_tasks(items: list[dict]) -> list[ImageTask]:
    tasks: list[ImageTask] = []
    for item in items:
        item_stem = safe_stem(item["name"], item["product_code"])
        illustration = item.get("illustration", "")
        if illustration:
            tasks.append(
                ImageTask(
                    url=illustration,
                    stem=f"Illustration_{item_stem}",
                )
            )
        for index, url in enumerate(item.get("images", []), start=1):
            tasks.append(
                ImageTask(
                    url=url,
                    stem=f"Detail_{item_stem}_{index}",
                )
            )
    stems = [task.stem for task in tasks]
    duplicates = sorted({stem for stem in stems if stems.count(stem) > 1})
    if duplicates:
        raise ValueError(f"duplicate destination filenames: {duplicates}")
    return tasks


def populate_local_paths(items: list[dict]) -> None:
    """Attach repository-relative paths for every downloaded detail image."""
    for item in items:
        item_stem = safe_stem(item["name"], item["product_code"])

        illustration = item.get("illustration", "")
        if illustration:
            illustration_task = ImageTask(
                url=illustration,
                stem=f"Illustration_{item_stem}",
            )
            illustration_path = existing_image(illustration_task)
            if illustration_path is None:
                raise FileNotFoundError(
                    f"missing downloaded illustration: {illustration_task.stem}"
                )
            item["local_illustration"] = (
                f"./{illustration_path.relative_to(JSON_PATH.parent).as_posix()}"
            )
        else:
            item["local_illustration"] = ""

        local_images: list[str] = []
        for index, url in enumerate(item.get("images", []), start=1):
            image_task = ImageTask(
                url=url,
                stem=f"Detail_{item_stem}_{index}",
            )
            image_path = existing_image(image_task)
            if image_path is None:
                raise FileNotFoundError(
                    f"missing downloaded detail image: {image_task.stem}"
                )
            local_images.append(
                f"./{image_path.relative_to(JSON_PATH.parent).as_posix()}"
            )
        item["local_images"] = local_images


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")

    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    tasks = build_tasks(payload["detail_list"])
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    results: list[Path] = []
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download, task, args.force): task for task in tasks}
        for completed, future in enumerate(as_completed(futures), start=1):
            task = futures[future]
            try:
                results.append(future.result())
            except Exception as error:
                failures.append(f"{task.stem}: {error}")
            if completed % 50 == 0 or completed == len(tasks):
                print(f"processed {completed}/{len(tasks)} images", flush=True)

    if failures:
        raise RuntimeError("download failures:\n" + "\n".join(failures))

    populate_local_paths(payload["detail_list"])
    JSON_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"downloaded or reused {len(results)} images in {IMAGE_DIR}")
    print(f"updated local image paths in {JSON_PATH}")


if __name__ == "__main__":
    main()
