"""Download selected Google Fonts into project font assets.

The game uses local font files through pygame.font.Font(). This tool downloads
approved Google Fonts from the official google/fonts repository and stores
them under assets/fonts so GUI builders can reference stable local paths.
"""

from __future__ import annotations

import argparse
import os
from urllib.error import URLError
from urllib.request import urlopen


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(PROJECT_DIR, "assets", "fonts")
GOOGLE_FONTS_RAW = "https://raw.githubusercontent.com/google/fonts/main"


FONT_REGISTRY = {
    "ingrid-darling": {
        "family": "Ingrid Darling",
        "license": "OFL-1.1",
        "directory": "ofl/ingriddarling",
        "files": (
            "IngridDarling-Regular.ttf",
            "OFL.txt",
        ),
    },
}


def main():
    args = parse_args()
    if args.list:
        print_available_fonts()
        return

    font_key = normalize_font_key(args.font)
    font_info = get_font_info(font_key)
    downloaded_paths = download_font(font_key, font_info)
    print(f"Downloaded {font_info['family']} ({font_info['license']}):")
    for path in downloaded_paths:
        print(f"  {os.path.relpath(path, PROJECT_DIR)}")


def parse_args():
    parser = argparse.ArgumentParser(description="Download Google Font files into assets/fonts.")
    parser.add_argument(
        "font",
        nargs="?",
        default="ingrid-darling",
        help="Font key to download, for example: ingrid-darling",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List fonts known by this project tool.",
    )
    return parser.parse_args()


def print_available_fonts():
    for font_key, font_info in sorted(FONT_REGISTRY.items()):
        print(f"{font_key}: {font_info['family']} ({font_info['license']})")


def normalize_font_key(font_key):
    return font_key.strip().lower().replace(" ", "-").replace("_", "-")


def get_font_info(font_key):
    try:
        return FONT_REGISTRY[font_key]
    except KeyError as error:
        available = ", ".join(sorted(FONT_REGISTRY))
        raise SystemExit(f"Unknown font: {font_key}. Available: {available}") from error


def download_font(font_key, font_info):
    output_dir = os.path.join(FONTS_DIR, font_key)
    os.makedirs(output_dir, exist_ok=True)

    downloaded_paths = []
    for file_name in font_info["files"]:
        url = f"{GOOGLE_FONTS_RAW}/{font_info['directory']}/{file_name}"
        output_path = os.path.join(output_dir, file_name)
        download_file(url, output_path)
        downloaded_paths.append(output_path)
    return downloaded_paths


def download_file(url, output_path):
    try:
        with urlopen(url, timeout=20) as response:
            data = response.read()
    except URLError as error:
        raise SystemExit(f"Download failed: {url}\n{error}") from error

    with open(output_path, "wb") as file:
        file.write(data)


if __name__ == "__main__":
    main()
