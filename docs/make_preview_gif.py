"""Build docs/preview.gif from the Original/Pip idle cycle and sample quota bars."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT / "skins" / "original"
OUT = ROOT / "docs" / "preview.gif"
BG = (11, 21, 32, 255)
BUBBLE = (16, 36, 58, 255)
OUTLINE = (42, 107, 122, 255)
TRACK = (22, 48, 68, 255)
OK = (61, 220, 151, 255)
MID = (224, 179, 106, 255)
LABEL = (158, 216, 224, 255)
PCT = (215, 246, 250, 255)
ROWS = (
    ("SuperGrok", 72, OK),
    ("Grok Bot", 61, OK),
    ("Cursor 模型", 48, MID),
    ("其他模型", 84, OK),
    ("Codex", 67, OK),
)


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = (
        "C:\\Windows\\Fonts\\msyhbd.ttc" if bold else "C:\\Windows\\Fonts\\msyh.ttc",
        "C:\\Windows\\Fonts\\msyhbd.ttf" if bold else "C:\\Windows\\Fonts\\msyh.ttf",
        "C:\\Windows\\Fonts\\segoeui.ttf",
    )
    for name in names:
        path = Path(name)
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _crop_sprite(frame: Image.Image) -> Image.Image:
    alpha = frame.getchannel("A")
    box = alpha.getbbox()
    return frame.crop(box) if box else frame


def _bar_color(remaining: int) -> tuple[int, int, int, int]:
    if remaining <= 20:
        return (224, 90, 90, 255)
    if remaining <= 50:
        return MID
    return OK


def main() -> None:
    spec = json.loads((SKIN / "pet.json").read_text(encoding="utf-8"))
    atlas = spec["atlas"]
    idle = spec["animations"]["idle"]
    wave = spec["animations"]["waving"]
    sheet = Image.open(SKIN / spec["spritesheetPath"]).convert("RGBA")
    cell_w = int(atlas["cellWidth"])
    cell_h = int(atlas["cellHeight"])

    def cells(anim: dict) -> list[Image.Image]:
        row = int(anim["row"])
        out = []
        for index in range(int(anim["frames"])):
            box = (
                index * cell_w,
                row * cell_h,
                (index + 1) * cell_w,
                (row + 1) * cell_h,
            )
            out.append(_crop_sprite(sheet.crop(box)))
        return out

    sprites = cells(idle) * 2 + cells(wave)
    delays = [int(idle["ms"])] * (int(idle["frames"]) * 2) + [int(wave["ms"])] * int(wave["frames"])
    sprite_w = max(img.width for img in sprites)
    sprite_h = max(img.height for img in sprites)

    pad = 18
    bubble_w = 292
    row_h = 36
    bubble_top = 16
    bubble_h = bubble_top + len(ROWS) * row_h + 12
    width = pad * 2 + bubble_w
    height = pad + bubble_h + 8 + sprite_h + pad
    title_font = _font(13, bold=True)
    pct_font = _font(13, bold=True)

    frames: list[Image.Image] = []
    for sprite in sprites:
        canvas = Image.new("RGBA", (width, height), BG)
        draw = ImageDraw.Draw(canvas)
        bx0, by0 = pad, pad
        bx1, by1 = bx0 + bubble_w, by0 + bubble_h
        draw.rounded_rectangle((bx0 + 3, by0 + 4, bx1 + 3, by1 + 4), 18, fill=(10, 24, 38, 255))
        draw.rounded_rectangle((bx0, by0, bx1, by1), 18, fill=BUBBLE, outline=OUTLINE, width=2)
        for index, (name, remaining, _) in enumerate(ROWS):
            top = by0 + bubble_top + index * row_h
            draw.text((bx0 + 16, top), name, font=title_font, fill=LABEL)
            pct = f"{remaining}%"
            tw = draw.textlength(pct, font=pct_font)
            draw.text((bx1 - 16 - tw, top), pct, font=pct_font, fill=PCT)
            bar_y = top + 18
            bar = (bx0 + 16, bar_y, bx1 - 16, bar_y + 8)
            draw.rounded_rectangle(bar, 4, fill=TRACK)
            fill_w = int((bar[2] - bar[0]) * remaining / 100)
            if fill_w > 6:
                draw.rounded_rectangle((bar[0], bar[1], bar[0] + fill_w, bar[3]), 4, fill=_bar_color(remaining))
        x = pad + (bubble_w - sprite.width) // 2
        y = pad + bubble_h + 8 + (sprite_h - sprite.height)
        canvas.alpha_composite(sprite, (x, y))
        frames.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE, colors=128, dither=Image.Dither.NONE))

    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=delays,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(frames)} frames)")


if __name__ == "__main__":
    main()
