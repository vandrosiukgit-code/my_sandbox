"""Build the reversible bottom-player attack overlay sprite sheet."""

import argparse
from pathlib import Path

from PIL import Image, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "assets" / "main_screen" / "player_attack"
FRAMES_DIR = OUTPUT_DIR / "frames"
ATTACK_REFERENCE_PATH = OUTPUT_DIR / "attack_overlay_reference.png"
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


def load_endpoint(path):
    with Image.open(path) as source:
        image = source.convert("RGBA")
    if image.size != CANVAS_SIZE:
        raise ValueError(f"Endpoint canvas must be {CANVAS_SIZE}: {path}")
    if image.getchannel("A").getbbox() is None:
        raise ValueError(f"Endpoint has no visible pixels: {path}")
    return clean_hidden_rgb(image)


def apply_opacity(base, opacity):
    frame = base.copy()
    frame.putalpha(base.getchannel("A").point(lambda value: round(value * opacity)))
    return clean_hidden_rgb(frame)


def export_reference(source_path):
    with Image.open(source_path) as source:
        normalized = ImageOps.fit(
            source.convert("RGBA"),
            CANVAS_SIZE,
            method=Image.Resampling.LANCZOS,
        )
    normalized = clean_hidden_rgb(normalized)
    normalized.save(ATTACK_REFERENCE_PATH, optimize=True)


def main(source_path=None):
    if source_path is not None:
        export_reference(source_path)
    attack = load_endpoint(ATTACK_REFERENCE_PATH)

    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    for stale_frame_path in FRAMES_DIR.glob("frame_*.png"):
        stale_frame_path.unlink()
    frames = []
    for index, opacity in enumerate(FRAME_OPACITIES):
        frame = apply_opacity(attack, opacity)
        frame.save(FRAMES_DIR / f"frame_{index:02d}.png", optimize=True)
        frames.append(frame)

    sprite_sheet = Image.new("RGBA", (CANVAS_SIZE[0], CANVAS_SIZE[1] * len(frames)), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sprite_sheet.alpha_composite(frame, (0, CANVAS_SIZE[1] * index))
    sprite_sheet.save(SPRITE_SHEET_PATH, optimize=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    arguments = parser.parse_args()
    main(arguments.source)
