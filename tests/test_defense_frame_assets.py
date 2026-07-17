import json
import unittest
from pathlib import Path

from PIL import Image, ImageChops


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRAMES_DIR = PROJECT_ROOT / "assets" / "main_screen" / "shield"
SPRITE_SHEET_PATH = FRAMES_DIR / "overlay.png"
MANIFEST_PATH = PROJECT_ROOT / "assets" / "resource_manifest.json"


class DefenseFrameAssetTests(unittest.TestCase):
    def get_frame_paths(self):
        return tuple(sorted(FRAMES_DIR.glob("shoot[0-9][0-9][0-9][0-9].png")))

    def test_eight_rgba_frames_use_one_canvas_and_clean_transparent_corners(self):
        paths = self.get_frame_paths()
        self.assertEqual(len(paths), 8)

        for path in paths:
            with Image.open(path) as source:
                image = source.convert("RGBA")
                self.assertEqual(source.format, "PNG")
                self.assertEqual(source.mode, "RGBA")
            self.assertEqual(image.size, (150, 150))
            self.assertTrue(all(image.getpixel(point) == (0, 0, 0, 0) for point in (
                (0, 0),
                (149, 0),
                (0, 149),
                (149, 149),
            )))
            green_spill = sum(
                1
                for red, green, blue, alpha in image.get_flattened_data()
                if alpha and green > max(red, blue) + 16
            )
            self.assertEqual(green_spill, 0, f"Green spill remains in {path.name}")

    def test_frame_visibility_increases_monotonically(self):
        maxima = []
        for path in self.get_frame_paths():
            with Image.open(path) as image:
                maxima.append(image.getchannel("A").getextrema()[1])

        self.assertTrue(all(first < second for first, second in zip(maxima, maxima[1:])))

    def test_sprite_sheet_matches_source_frames_and_manifest(self):
        frames = [Image.open(path).convert("RGBA") for path in self.get_frame_paths()]
        with Image.open(SPRITE_SHEET_PATH) as source:
            sheet = source.convert("RGBA")
        self.assertEqual(sheet.size, (150, 1200))
        for index, frame in enumerate(frames):
            crop = sheet.crop((0, index * 150, 150, (index + 1) * 150))
            self.assertIsNone(ImageChops.difference(crop, frame).getbbox())

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["resources"]
        resource = manifest["main_screen.player_defense.overlay"]
        self.assertEqual(resource["path"], "main_screen/shield/overlay.png")
        self.assertEqual((resource["frame_width"], resource["frame_height"]), (150, 150))


if __name__ == "__main__":
    unittest.main()
