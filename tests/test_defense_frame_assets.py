import json
import unittest
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPRITE_SHEET_PATH = PROJECT_ROOT / "assets" / "main_screen" / "shield" / "overlay.png"
MANIFEST_PATH = PROJECT_ROOT / "assets" / "resource_manifest.json"
FRAME_SIZE = (150, 150)
EXPECTED_FRAME_COUNT = 8


def load_runtime_frames():
    resources = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["resources"]
    resource = resources["main_screen.player_defense.overlay"]
    frame_size = (resource["frame_width"], resource["frame_height"])
    with Image.open(SPRITE_SHEET_PATH) as source:
        source.load()
        if source.format != "PNG" or source.mode != "RGBA":
            raise AssertionError("Defense sprite sheet must be a native RGBA PNG")
        sheet = source.copy()
    if sheet.width != frame_size[0] or sheet.height % frame_size[1]:
        raise AssertionError("Defense sprite sheet does not match manifest frame geometry")
    return resource, tuple(
        sheet.crop((0, index * frame_size[1], frame_size[0], (index + 1) * frame_size[1]))
        for index in range(sheet.height // frame_size[1])
    )


class DefenseFrameAssetTests(unittest.TestCase):
    def test_runtime_sheet_has_eight_clean_rgba_frames(self):
        resource, frames = load_runtime_frames()
        self.assertEqual(resource["path"], "main_screen/shield/overlay.png")
        self.assertEqual((resource["frame_width"], resource["frame_height"]), FRAME_SIZE)
        self.assertEqual(len(frames), EXPECTED_FRAME_COUNT)
        for index, image in enumerate(frames):
            self.assertEqual(image.size, FRAME_SIZE)
            self.assertTrue(all(image.getpixel(point) == (0, 0, 0, 0) for point in (
                (0, 0), (149, 0), (0, 149), (149, 149),
            )))
            green_spill = sum(
                1
                for red, green, blue, alpha in image.get_flattened_data()
                if alpha and green > max(red, blue) + 16
            )
            self.assertEqual(green_spill, 0, f"Green spill remains in runtime frame {index}")

    def test_frame_visibility_increases_monotonically(self):
        _resource, frames = load_runtime_frames()
        maxima = [image.getchannel("A").getextrema()[1] for image in frames]
        self.assertTrue(all(first < second for first, second in zip(maxima, maxima[1:])))


if __name__ == "__main__":
    unittest.main()
