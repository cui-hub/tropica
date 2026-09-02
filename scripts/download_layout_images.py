#!/usr/bin/env python3
"""Download Tropica layout images and populate formatted local paths."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Final

try:
    from .download_plant_covers import (
        encode_url,
        image_extension,
        is_valid_image,
        source_extension,
    )
except ImportError:
    from download_plant_covers import (
        encode_url,
        image_extension,
        is_valid_image,
        source_extension,
    )


ROOT: Final = Path(__file__).resolve().parents[1]
JSON_PATH: Final = ROOT / "formatted" / "layout-detail-list.json"
IMAGE_DIR: Final = ROOT / "formatted" / "assets" / "images"
KNOWN_EXTENSIONS: Final = (".png", ".jpg", ".gif", ".webp", ".bmp")


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
            "Referer": "https://tropica.com/en/inspiration/",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
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
        layout_code = item["layout_code"]
        for index, url in enumerate(item["images"], start=1):
            tasks.append(ImageTask(url=url, stem=f"Layout_{layout_code}_{index}"))
        if item["planting_plan"]:
            tasks.append(
                ImageTask(
                    url=item["planting_plan"],
                    stem=f"LayoutPlan_{layout_code}",
                )
            )
    stems = [task.stem for task in tasks]
    duplicates = sorted({stem for stem in stems if stems.count(stem) > 1})
    if duplicates:
        raise ValueError(f"duplicate destination filenames: {duplicates}")
    return tasks


def local_path(path: Path) -> str:
    return f"./{path.relative_to(JSON_PATH.parent).as_posix()}"


def populate_local_paths(items: list[dict]) -> None:
    for item in items:
        layout_code = item["layout_code"]
        local_images: list[str] = []
        for index, url in enumerate(item["images"], start=1):
            task = ImageTask(url=url, stem=f"Layout_{layout_code}_{index}")
            path = existing_image(task)
            if path is None:
                raise FileNotFoundError(f"missing downloaded layout image: {task.stem}")
            local_images.append(local_path(path))
        item["local_images"] = local_images

        if item["planting_plan"]:
            task = ImageTask(
                url=item["planting_plan"],
                stem=f"LayoutPlan_{layout_code}",
            )
            path = existing_image(task)
            if path is None:
                raise FileNotFoundError(f"missing downloaded planting plan: {task.stem}")
            item["local_planting_plan"] = local_path(path)
        else:
            item["local_planting_plan"] = ""


def write_json(payload: object) -> None:
    temporary = JSON_PATH.with_suffix(JSON_PATH.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(JSON_PATH)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")

    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    items = payload["detail_list"]
    tasks = build_tasks(items)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download, task, args.force): task for task in tasks}
        for completed, future in enumerate(as_completed(futures), start=1):
            task = futures[future]
            try:
                future.result()
            except Exception as error:
                failures.append(f"{task.stem}: {error}")
            if completed % 50 == 0 or completed == len(tasks):
                print(f"processed {completed}/{len(tasks)} images", flush=True)

    if failures:
        raise RuntimeError("download failures:\n" + "\n".join(failures))
    populate_local_paths(items)
    write_json(payload)
    print(f"downloaded or reused {len(tasks)} images in {IMAGE_DIR}")
    print(f"updated local layout image paths in {JSON_PATH}")


if __name__ == "__main__":
    main()
