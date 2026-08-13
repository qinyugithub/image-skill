#!/usr/bin/env python3
"""把无字插画与 job.json 中的中文原文合成为标准漫画。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_job(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_crlf(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(text.replace("\r\n", "\n"))


def resolve_font(job: dict, override: str | None) -> Path:
    candidates = [
        override,
        os.environ.get("COMIC_FONT_PATH"),
        job.get("layout", {}).get("font_path"),
        r"C:\Windows\Fonts\simkai.ttf",
        r"C:\Windows\Fonts\STKAITI.TTF",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    raise FileNotFoundError("找不到可用中文字体。可设置 COMIC_FONT_PATH 或传入 --font。")


def fit_font_size(font_path: Path, lines: list[str], maximum: int, minimum: int = 36) -> int:
    for size in range(maximum, minimum - 1, -1):
        font = ImageFont.truetype(str(font_path), size)
        if all(font.getlength(line) <= 680 for line in lines):
            return size
    raise ValueError("文案过长，无法在 800 像素画布中排版；请增加分行。")


def glyph_mask(font_path: Path, char: str, size: int, angle: float) -> Image.Image:
    font = ImageFont.truetype(str(font_path), size)
    box = font.getbbox(char, stroke_width=1)
    width = max(1, box[2] - box[0])
    height = max(1, box[3] - box[1])
    pad = 16
    mask = Image.new("L", (width + pad * 2, height + pad * 2), 0)
    draw = ImageDraw.Draw(mask)
    draw.text(
        (pad - box[0], pad - box[1]),
        char,
        font=font,
        fill=255,
        stroke_width=1,
        stroke_fill=255,
    )
    mask = mask.filter(ImageFilter.MaxFilter(3))
    mask = mask.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    bounds = mask.getbbox()
    return mask.crop(bounds) if bounds else mask


def draw_caption(canvas: Image.Image, lines: list[str], font_path: Path, start_y: int, end_y: int) -> dict:
    max_by_count = {1: 76, 2: 72, 3: 68, 4: 60, 5: 54}[len(lines)]
    size = fit_font_size(font_path, lines, max_by_count)
    rng = random.Random(20260813)
    line_step = min(116, max(78, int((end_y - start_y) / max(len(lines), 1))))
    block_height = (len(lines) - 1) * line_step + int(size * 1.12)
    available = end_y - start_y
    first_y = start_y + max(0, int((available - block_height) * 0.22))

    rendered_lines = []
    for line_index, text in enumerate(lines):
        glyphs = []
        for char in text:
            char_size = size + rng.randint(-2, 2)
            mask = glyph_mask(font_path, char, char_size, rng.uniform(-1.3, 1.3))
            glyphs.append((mask, rng.randint(2, 5)))
        total_width = sum(mask.width + spacing for mask, spacing in glyphs) - glyphs[-1][1]
        if total_width > 710:
            raise ValueError(f"第 {line_index + 1} 行排版后过宽，请增加分行：{text}")
        x = int((canvas.width - total_width) / 2)
        y = first_y + line_index * line_step
        for mask, spacing in glyphs:
            canvas.paste((8, 8, 8), (x, y + rng.randint(-3, 3)), mask)
            x += mask.width + spacing
        rendered_lines.append({"text": text, "y": y, "width": total_width})
    return {"font_size": size, "line_step": line_step, "lines": rendered_lines}


def main() -> int:
    parser = argparse.ArgumentParser(description="合成 800×1200 水彩漫画与准确中文文案")
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--input", type=Path, help="无字插画；默认读取 job.json")
    parser.add_argument("--output", type=Path, help="最终图片；默认写入 job.json")
    parser.add_argument("--font", help="中文字体文件，可覆盖默认字体")
    args = parser.parse_args()

    job_path = args.job.resolve()
    job = read_job(job_path)
    input_path = (args.input or Path(job["paths"]["illustration"])).resolve()
    output_path = (args.output or Path(job["paths"]["final"])).resolve()
    manifest_path = output_path.with_name(output_path.stem + ".manifest.json")
    lines = job.get("caption_lines", [])
    if not 1 <= len(lines) <= 5 or any(not line for line in lines):
        raise ValueError("job.json 中的 caption_lines 必须包含 1～5 个非空字符串")
    if not input_path.is_file():
        raise FileNotFoundError(f"找不到无字插画：{input_path}")

    layout = job.get("layout", {})
    width = int(layout.get("width", 800))
    height = int(layout.get("height", 1200))
    if (width, height) != (800, 1200):
        raise ValueError("当前系列的最终画布必须固定为 800×1200")

    source = Image.open(input_path).convert("RGB")
    canvas = ImageOps.fit(source, (width, height), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    font_path = resolve_font(job, args.font)
    caption_layout = draw_caption(
        canvas,
        lines,
        font_path,
        int(layout.get("caption_start_y", 675)),
        int(layout.get("caption_end_y", 1065)),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "job": str(job_path),
        "prompt_version": job.get("prompt_version"),
        "profile": job.get("profile"),
        "caption_lines": lines,
        "caption_text": "\n".join(lines),
        "font": str(font_path),
        "caption_layout": caption_layout,
        "source": str(input_path),
        "source_sha256": sha256(input_path),
        "output": str(output_path),
        "output_sha256": sha256(output_path),
        "size": [width, height],
    }
    write_crlf(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(output_path), "manifest": str(manifest_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
