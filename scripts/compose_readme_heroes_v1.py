"""Compose 16:9 laptop-chrome heroes from portrait browser captures (contain, never stretch)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CAND = Path(__file__).resolve().parents[1] / "docs" / "assets" / "_candidates"
OUT = Path(__file__).resolve().parents[1] / "docs" / "assets"

FRAME_W, FRAME_H = 1600, 1000
PAD = 48
TITLE_H = 40
RADIUS = 18


def make_frame(src: Path, title: str, dest: Path) -> None:
    shot = Image.open(src).convert("RGBA")
    canvas = Image.new("RGBA", (FRAME_W, FRAME_H), (12, 12, 14, 255))
    draw = ImageDraw.Draw(canvas)
    win = (PAD, PAD, FRAME_W - PAD, FRAME_H - PAD)
    draw.rounded_rectangle(win, radius=RADIUS, fill=(22, 22, 26, 255), outline=(55, 55, 62, 255), width=2)
    draw.rounded_rectangle((PAD, PAD, FRAME_W - PAD, PAD + TITLE_H), radius=RADIUS, fill=(32, 32, 38, 255))
    draw.rectangle((PAD, PAD + TITLE_H - 12, FRAME_W - PAD, PAD + TITLE_H), fill=(32, 32, 38, 255))
    for i, col in enumerate([(255, 95, 87), (255, 189, 46), (40, 200, 64)]):
        x = PAD + 18 + i * 18
        draw.ellipse((x, PAD + 13, x + 12, PAD + 25), fill=col)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
    draw.text((PAD + 80, PAD + 10), title, fill=(200, 200, 210, 255), font=font)
    content = (PAD + 10, PAD + TITLE_H + 8, FRAME_W - PAD - 10, FRAME_H - PAD - 10)
    cw, ch = content[2] - content[0], content[3] - content[1]
    draw.rectangle(content, fill=(0, 0, 0, 255))
    scale = min(cw / shot.width, ch / shot.height)
    nw, nh = max(1, int(shot.width * scale)), max(1, int(shot.height * scale))
    shot2 = shot.resize((nw, nh), Image.Resampling.LANCZOS)
    x = content[0] + (cw - nw) // 2
    y = content[1] + (ch - nh) // 2
    canvas.alpha_composite(shot2, (x, y))
    rgb = canvas.convert("RGB")
    rgb.save(dest, "PNG", optimize=True)
    print(f"wrote {dest.name} {rgb.size} {dest.stat().st_size}")


def main() -> None:
    make_frame(CAND / "ha-world.png", "Hardware Atom — World · Dual Safe/Hostile", OUT / "hero-world.png")
    make_frame(CAND / "ha-desk-mission.png", "Hardware Atom — Mission · Dual sinkage", OUT / "hero-mission.png")
    make_frame(CAND / "hexapod.png", "Hardware Atom — Body / World viewer", OUT / "hero-body.png")


if __name__ == "__main__":
    main()
