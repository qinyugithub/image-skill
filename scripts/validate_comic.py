#!/usr/bin/env python3
"""对最终漫画进行低成本结构验收，并核对文案清单与文件哈希。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageStat


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def dark_pixel_ratio(image: Image.Image, box: tuple[int, int, int, int], threshold: int = 90) -> float:
    gray = image.crop(box).convert("L")
    histogram = gray.histogram()
    dark = sum(histogram[:threshold])
    return dark / max(1, gray.width * gray.height)


def main() -> int:
    parser = argparse.ArgumentParser(description="验收漫画尺寸、文案清单、留白和文件完整性")
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    job_path = args.job.resolve()
    job = read_json(job_path)
    image_path = (args.image or Path(job["paths"]["final"])).resolve()
    manifest_path = (args.manifest or image_path.with_name(image_path.stem + ".manifest.json")).resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not image_path.is_file():
        errors.append(f"找不到最终图片：{image_path}")
    if not manifest_path.is_file():
        errors.append(f"找不到合成清单：{manifest_path}")
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    manifest = read_json(manifest_path)
    if manifest.get("caption_lines") != job.get("caption_lines"):
        errors.append("合成清单中的文案与 job.json 不一致")
    if manifest.get("output_sha256") != sha256(image_path):
        errors.append("最终图片哈希与合成清单不一致，文件可能在合成后被修改")

    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        if rgb.size != (800, 1200):
            errors.append(f"最终尺寸应为 800×1200，实际为 {rgb.width}×{rgb.height}")

        upper_dark = dark_pixel_ratio(rgb, (0, 40, 800, 650))
        caption_dark = dark_pixel_ratio(rgb, (50, 650, 750, 1090))
        if upper_dark < 0.002:
            errors.append("上半部几乎没有可见插画")
        if caption_dark < 0.004:
            errors.append("下方文案区几乎没有可见文字")
        if caption_dark > 0.22:
            warnings.append("文案区墨色占比过高，可能存在插画侵入或文案过密")

        corner_boxes = [
            (0, 0, 60, 60),
            (740, 0, 800, 60),
            (0, 1140, 60, 1200),
            (740, 1140, 800, 1200),
        ]
        corner_means = [sum(ImageStat.Stat(rgb.crop(box)).mean) / 3 for box in corner_boxes]
        if min(corner_means) < 235:
            warnings.append("至少一个角落不是接近白色，可能失去样例的大留白结构")

    result = {
        "ok": not errors,
        "image": str(image_path),
        "caption_lines": job.get("caption_lines"),
        "checks": {
            "size": "800x1200",
            "hash_matches_manifest": manifest.get("output_sha256") == sha256(image_path),
            "upper_dark_ratio": round(upper_dark, 6),
            "caption_dark_ratio": round(caption_dark, 6),
        },
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
