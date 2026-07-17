"""Build the reversible bottom-player attack overlay sprite sheet."""

import argparse
from pathlib import Path

from PIL import Image, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "assets" / "main_screen" / "player_attack"
SPRITE_SHEET_PATH = OUTPUT_DIR / "overlay.png"

CANVAS_SIZE = (1024, 768)
FRAME_OPACITIES = (
    0.0,
    0.025,
    0.07,
    0.14,
    0.23,
    0.34,
    0.47,
    0.60,
    0.72,
    0.82,
    0.90,
    0.96,
    1.0,
)


def clean_hidden_rgb(image):
    pixels = []
    for red, green, blue, alpha in image.get_flattened_data():
        pixels.append((red, green, blue, alpha) if alpha else (0, 0, 0, 0))
    cleaned = Image.new("RGBA", image.size)
    cleaned.putdata(pixels)
    return cleaned


def load_endpoint(source_path=None):
    path = source_path or SPRITE_SHEET_PATH
    with Image.open(path) as source:
        image = source.convert("RGBA")
    if source_path is None:
        expected_sheet_size = (CANVAS_SIZE[0], CANVAS_SIZE[1] * len(FRAME_OPACITIES))
        if image.size != expected_sheet_size:
            raise ValueError(f"Existing sprite sheet must be {expected_sheet_size}: {path}")
        image = image.crop((0, image.height - CANVAS_SIZE[1], CANVAS_SIZE[0], image.height))
    elif image.size != CANVAS_SIZE:
        image = ImageOps.fit(image, CANVAS_SIZE, method=Image.Resampling.LANCZOS)
    if image.getchannel("A").getbbox() is None:
        raise ValueError(f"Endpoint has no visible pixels: {source_path}")
    return clean_hidden_rgb(image)


def apply_opacity(base, opacity):
    frame = base.copy()
    frame.putalpha(base.getchannel("A").point(lambda value: round(value * opacity)))
    return clean_hidden_rgb(frame)


def main(source_path=None):
    attack = load_endpoint(source_path)
    frames = [apply_opacity(attack, opacity) for opacity in FRAME_OPACITIES]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sprite_sheet = Image.new("RGBA", (CANVAS_SIZE[0], CANVAS_SIZE[1] * len(frames)), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sprite_sheet.alpha_composite(frame, (0, CANVAS_SIZE[1] * index))
    sprite_sheet.save(SPRITE_SHEET_PATH, optimize=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    arguments = parser.parse_args()
    main(arguments.source)
