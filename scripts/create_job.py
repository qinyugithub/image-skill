#!/usr/bin/env python3
"""为对话式漫画工作流创建可追溯任务和固定提示词。"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


PROFILES = {
    "daily": [
        "assets/daily-style-anchor.png",
        "assets/references/daily-14.png",
        "assets/references/daily-20.png",
    ],
    "poetic": [
        "assets/references/poetic-10.png",
        "assets/references/poetic-11.png",
        "assets/references/poetic-12.png",
    ],
    "metaphor": [
        "assets/references/metaphor-1.png",
        "assets/references/metaphor-3.png",
        "assets/references/metaphor-8.png",
    ],
    "vivid": [
        "assets/references/vivid-21.png",
        "assets/references/vivid-24.png",
        "assets/references/vivid-25.png",
    ],
}

PROMPT_VERSION = "chat-comic-v1"


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def project_root() -> Path:
    return Path.cwd().resolve()


def safe_slug(value: str) -> str:
    value = re.sub(r"[^\w\-]+", "-", value.strip(), flags=re.UNICODE)
    return value.strip("-")[:40] or "comic"


def write_crlf(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(text.replace("\r\n", "\n"))


def build_prompt(data: dict) -> str:
    avoid = "、".join(data["avoid"]) if data["avoid"] else "无额外要求"
    return f"""Use case: illustration-story
Asset type: vertical single-panel Chinese watercolor comic illustration, without caption text
Input images: Images 1-3 are style and layout references only. Learn only their shared loose ink-and-watercolor language, simplified comic forms, white-paper negative space and handmade imperfections. Ignore and do not reproduce any words from the reference images.
Primary request: {data['scene']}
Scene/backdrop: nearly pure white watercolor paper. Include only the minimum subjects and props needed to communicate this single moment clearly.
Style/medium: spontaneous black ink outlines with visibly uneven pressure; loose transparent watercolor washes; natural pigment blooms, dry-brush texture, small unpainted gaps and slightly imperfect proportions; understated Chinese editorial comic; not polished digital illustration.
Composition/framing: 2:3 portrait poster. Place one compact illustration centered within the upper 52% of the canvas. Keep the entire lower 43% completely empty clean white for later Chinese caption typesetting. Preserve generous white margins around the drawing.
Lighting/mood: {data['mood']}.
Color palette: black ink, restrained pale watercolor, with {data['accent']} as the main accent color; avoid excessive saturation.
Narrative constraint: express exactly one readable action, emotional beat or visual metaphor. Do not invent extra characters, props or story beats.
Text constraint: image only. Absolutely no words, letters, Chinese characters, numbers, captions, speech bubbles, pseudo-text strokes, decorative border, logo, signature or watermark anywhere in the image. The lower caption area must contain no marks at all.
Avoid: photorealism, 3D, glossy anime rendering, vector-clean lines, dense background, full-bleed color, panel borders, dialogue bubbles, extra characters, extra props. User exclusions: {avoid}.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="创建无 API 的对话式漫画任务")
    parser.add_argument("--scene", required=True, help="画面内容")
    parser.add_argument("--line", action="append", required=True, dest="lines", help="底部文案的一行，可重复 2～5 次")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="daily")
    parser.add_argument("--mood", default="克制、生活化、轻微冷幽默")
    parser.add_argument("--accent", default="浅蓝色")
    parser.add_argument("--avoid", action="append", default=[])
    parser.add_argument("--slug", default="comic")
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()

    lines = [line.strip() for line in args.lines if line.strip()]
    if not 1 <= len(lines) <= 5:
        parser.error("文案必须为 1～5 行，推荐 2～5 行")

    root = project_root()
    output_root = (args.output_root or root / "output" / "comics" / "jobs").resolve()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_dir = output_root / f"{stamp}-{safe_slug(args.slug)}"
    suffix = 2
    while job_dir.exists():
        job_dir = output_root / f"{stamp}-{safe_slug(args.slug)}-v{suffix}"
        suffix += 1
    job_dir.mkdir(parents=True)

    references = [(skill_root() / item).resolve() for item in PROFILES[args.profile]]
    missing = [str(path) for path in references if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少风格参考图：" + "；".join(missing))

    data = {
        "schema_version": 1,
        "prompt_version": PROMPT_VERSION,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scene": args.scene.strip(),
        "caption_lines": lines,
        "caption_text": "\n".join(lines),
        "profile": args.profile,
        "mood": args.mood.strip(),
        "accent": args.accent.strip(),
        "avoid": [item.strip() for item in args.avoid if item.strip()],
        "reference_images": [str(path) for path in references],
        "layout": {
            "width": 800,
            "height": 1200,
            "illustration_max_height_ratio": 0.52,
            "caption_start_y": 675,
            "caption_end_y": 1065,
            "font_path": "",
        },
        "paths": {
            "job_dir": str(job_dir.resolve()),
            "prompt": str((job_dir / "prompt.txt").resolve()),
            "illustration": str((job_dir / "illustration.png").resolve()),
            "final": str((job_dir / "final.png").resolve()),
            "manifest": str((job_dir / "final.manifest.json").resolve()),
        },
    }

    prompt = build_prompt(data)
    write_crlf(job_dir / "prompt.txt", prompt)
    write_crlf(job_dir / "job.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    print(json.dumps({
        "job": str((job_dir / "job.json").resolve()),
        "prompt": str((job_dir / "prompt.txt").resolve()),
        "reference_images": data["reference_images"],
        "illustration": data["paths"]["illustration"],
        "final": data["paths"]["final"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
