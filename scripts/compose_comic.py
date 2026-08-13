#!/usr/bin/env python3
"""把无字插画与 job.json 中的中文原文合成为标准漫画。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


SENTENCE_ENDINGS = "。！？；"
CLOSING_PUNCTUATION = "，。！？；：、）》】」』…"
OPENING_PUNCTUATION = "（《【「『"
PREFERRED_LINE_STARTS = "能会也就才而但却让把被给与和认"
PROTECTED_PAIRS = {"一天", "一年", "高估", "低估", "改变", "认真", "坚持", "带来"}


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
    bundled_ma_shan_zheng = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "MaShanZheng-Regular.ttf"
    candidates = [
        override,
        os.environ.get("COMIC_FONT_PATH"),
        job.get("layout", {}).get("font_path"),
        bundled_ma_shan_zheng,
        r"C:\Windows\Fonts\simkai.ttf",
        r"C:\Windows\Fonts\STKAITI.TTF",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    raise FileNotFoundError("找不到可用中文字体。可设置 COMIC_FONT_PATH 或传入 --font。")


def font_stroke_width(font_path: Path, size: int) -> int:
    if font_path.name.casefold() == "mashanzheng-regular.ttf":
        return max(1, round(size / 64))
    return 1


def line_metrics(font_path: Path, text: str, size: int) -> tuple[int, int, tuple[int, int, int, int]]:
    font = ImageFont.truetype(str(font_path), size)
    box = font.getbbox(text, anchor="ls", stroke_width=font_stroke_width(font_path, size))
    return max(1, box[2] - box[0]), max(1, box[3] - box[1]), box


def split_sentences(text: str) -> list[str]:
    segments: list[str] = []
    start = 0
    for index, character in enumerate(text):
        if character in SENTENCE_ENDINGS:
            segments.append(text[start:index + 1])
            start = index + 1
    if start < len(text):
        segments.append(text[start:])
    return [segment for segment in segments if segment]


def wrap_segment(font_path: Path, text: str, size: int, maximum_width: int) -> list[str]:
    if line_metrics(font_path, text, size)[0] <= maximum_width:
        return [text]

    widths = {
        (start, end): line_metrics(font_path, text[start:end], size)[0]
        for start in range(len(text))
        for end in range(start + 1, len(text) + 1)
    }
    for line_count in range(2, 6):
        target_width = line_metrics(font_path, text, size)[0] / line_count
        states: dict[tuple[int, int], tuple[float, list[str]]] = {(0, 0): (0.0, [])}
        for used in range(line_count):
            for (state_used, start), (cost, parts) in list(states.items()):
                if state_used != used:
                    continue
                remaining_lines = line_count - used - 1
                minimum_end = start + 1
                maximum_end = len(text) - remaining_lines
                for end in range(minimum_end, maximum_end + 1):
                    part = text[start:end]
                    if widths[(start, end)] > maximum_width:
                        continue
                    if end < len(text) and text[end - 1:end + 1] in PROTECTED_PAIRS:
                        continue
                    if part[0] in CLOSING_PUNCTUATION or part[-1] in OPENING_PUNCTUATION:
                        continue
                    visible_characters = len(part.rstrip(CLOSING_PUNCTUATION))
                    part_cost = (widths[(start, end)] - target_width) ** 2
                    if visible_characters <= 2:
                        part_cost += maximum_width ** 2
                    if end < len(text) and text[end] in PREFERRED_LINE_STARTS:
                        part_cost -= maximum_width ** 2 * 0.06
                    key = (used + 1, end)
                    candidate = (cost + part_cost, parts + [part])
                    if key not in states or candidate[0] < states[key][0]:
                        states[key] = candidate
        result = states.get((line_count, len(text)))
        if result:
            return result[1]
    return [text]


def wrap_caption(font_path: Path, source_lines: list[str], size: int, maximum_width: int) -> list[str]:
    wrapped: list[str] = []
    for source_line in source_lines:
        clauses = split_sentences(source_line)
        if len(clauses) == 1 and line_metrics(font_path, source_line, size)[0] <= maximum_width:
            wrapped.append(source_line)
            continue
        for clause in clauses:
            wrapped.extend(wrap_segment(font_path, clause, size, maximum_width))
    return wrapped


def fit_caption(font_path: Path, lines: list[str], start_y: int, end_y: int) -> dict:
    available_height = end_y - start_y
    for size in range(82, 39, -1):
        wrapped_lines = wrap_caption(font_path, lines, size, 600)
        if not 1 <= len(wrapped_lines) <= 5:
            continue
        metrics = [line_metrics(font_path, line, size) for line in wrapped_lines]
        line_gap = max(10, round(size * 0.12))
        block_height = sum(height for _, height, _ in metrics) + line_gap * (len(wrapped_lines) - 1)
        if max(width for width, _, _ in metrics) <= 700 and block_height <= available_height:
            return {
                "font_size": size,
                "line_gap": line_gap,
                "block_height": block_height,
                "metrics": metrics,
                "lines": wrapped_lines,
            }
    raise ValueError("文案过长或插画占用过多空间，无法在不遮挡画面的前提下排版。")


def render_line_mask(font_path: Path, text: str, size: int) -> Image.Image:
    font = ImageFont.truetype(str(font_path), size)
    stroke_width = font_stroke_width(font_path, size)
    width, height, box = line_metrics(font_path, text, size)
    pad = 8 + stroke_width
    mask = Image.new("L", (width + pad * 2, height + pad * 2), 0)
    draw = ImageDraw.Draw(mask)
    draw.text(
        (pad - box[0], pad - box[1]),
        text,
        font=font,
        fill=255,
        anchor="ls",
        stroke_width=stroke_width,
        stroke_fill=255,
    )
    bounds = mask.getbbox()
    return mask.crop(bounds) if bounds else mask


def find_illustration_bottom(image: Image.Image, maximum_y: int = 850) -> int:
    gray = image.convert("L")
    left, right = 35, image.width - 35
    active_rows: list[int] = []
    for y in range(40, min(maximum_y, image.height)):
        row = gray.crop((left, y, right, y + 1))
        dark_pixels = sum(row.histogram()[:245])
        if dark_pixels >= 12:
            active_rows.append(y)
    if not active_rows:
        return 0
    active = set(active_rows)
    stable_rows = [y for y in active_rows if sum((y + offset) in active for offset in range(-2, 3)) >= 3]
    return max(stable_rows or active_rows)


def draw_caption(
    canvas: Image.Image,
    lines: list[str],
    font_path: Path,
    requested_start_y: int,
    end_y: int,
    illustration_bottom_y: int,
) -> dict:
    safe_gap = 30
    start_y = max(requested_start_y, illustration_bottom_y + safe_gap)
    fitted = fit_caption(font_path, lines, start_y, end_y)
    size = fitted["font_size"]
    line_gap = fitted["line_gap"]
    display_lines = fitted["lines"]
    available = end_y - start_y
    first_y = start_y + max(0, round((available - fitted["block_height"]) * 0.18))

    rendered_lines = []
    y = first_y
    for text in display_lines:
        mask = render_line_mask(font_path, text, size)
        x = int((canvas.width - mask.width) / 2)
        canvas.paste((8, 8, 8), (x, y), mask)
        rendered_lines.append({"text": text, "x": x, "y": y, "width": mask.width, "height": mask.height})
        y += mask.height + line_gap
    return {
        "font_size": size,
        "font_stroke_width": font_stroke_width(font_path, size),
        "line_gap": line_gap,
        "illustration_bottom_y": illustration_bottom_y,
        "safe_caption_start_y": start_y,
        "source_lines": lines,
        "lines": rendered_lines,
    }


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
    illustration_bottom_y = find_illustration_bottom(canvas)
    layout_lines = lines if job.get("preserve_caption_line_breaks", False) else ["".join(lines)]
    caption_layout = draw_caption(
        canvas,
        layout_lines,
        font_path,
        int(layout.get("caption_start_y", 675)),
        max(1190, int(layout.get("caption_end_y", 1190))),
        illustration_bottom_y,
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
        "preserve_caption_line_breaks": job.get("preserve_caption_line_breaks", False),
        "rendered_caption_lines": [line["text"] for line in caption_layout["lines"]],
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
