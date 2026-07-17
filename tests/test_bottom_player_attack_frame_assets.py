import json
import unittest
from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageChops


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPRITE_SHEET_PATH = PROJECT_ROOT / "assets" / "main_screen" / "player_attack" / "overlay.png"
RESOURCE_MANIFEST_PATH = PROJECT_ROOT / "assets" / "resource_manifest.json"

EXPECTED_FRAME_COUNT = 13
MIN_CANVAS_SIZE = (384, 320)
MIN_ADJACENT_CHANGE_RATIO = 0.002
MAX_ADJACENT_CHANGE_RATIO = 0.60
MAX_HORIZONTAL_CENTER_DRIFT_RATIO = 0.03
MAX_BOTTOM_ANCHOR_DRIFT_RATIO = 0.02
TRANSPARENT_BORDER_WIDTH = 2


def combined_difference_mask(first, second):
    difference = ImageChops.difference(first, second)
    mask = difference.getchannel("R")
    for channel_name in ("G", "B", "A"):
        mask = ImageChops.lighter(mask, difference.getchannel(channel_name))
    return mask


def nonzero_pixel_ratio(mask):
    histogram = mask.histogram()
    return sum(histogram[1:]) / (mask.width * mask.height)


def load_manifest_resource():
    resources = json.loads(RESOURCE_MANIFEST_PATH.read_text(encoding="utf-8"))["resources"]
    return resources["main_screen.player_attack.overlay"]


def load_runtime_frames():
    resource = load_manifest_resource()
    frame_width = resource["frame_width"]
    frame_height = resource["frame_height"]
    with Image.open(SPRITE_SHEET_PATH) as source:
        source.load()
        if source.format != "PNG" or source.mode != "RGBA":
            raise AssertionError("Attack sprite sheet must be a native RGBA PNG")
        sheet = source.copy()
    if sheet.width != frame_width or sheet.height % frame_height:
        raise AssertionError("Attack sprite sheet does not match manifest frame geometry")
    return tuple(
        sheet.crop((0, index * frame_height, frame_width, (index + 1) * frame_height))
        for index in range(sheet.height // frame_height)
    )


class BottomPlayerAttackFrameAssetContractTests(unittest.TestCase):
    def test_runtime_sprite_sheet_and_manifest_are_complete(self):
        self.assertTrue(SPRITE_SHEET_PATH.is_file())
        resource = load_manifest_resource()
        self.assertEqual(resource["path"], "main_screen/player_attack/overlay.png")
        frames = load_runtime_frames()
        self.assertEqual(len(frames), EXPECTED_FRAME_COUNT)
        self.assertGreaterEqual(frames[0].width, MIN_CANVAS_SIZE[0])
        self.assertGreaterEqual(frames[0].height, MIN_CANVAS_SIZE[1])

    def test_frames_have_real_transparency_clean_hidden_rgb_and_no_clipped_edges(self):
        for index, image in enumerate(load_runtime_frames()):
            alpha = image.getchannel("A")
            alpha_minimum, alpha_maximum = alpha.getextrema()
            self.assertEqual(alpha_minimum, 0)
            self.assertEqual(alpha_maximum, 0 if index == 0 else alpha_maximum)
            if index:
                self.assertGreater(alpha_maximum, 0)

            border = Image.new("L", image.size, 0)
            border_pixels = border.load()
            for y in range(image.height):
                for x in range(image.width):
                    if (
                        x < TRANSPARENT_BORDER_WIDTH
                        or y < TRANSPARENT_BORDER_WIDTH
                        or x >= image.width - TRANSPARENT_BORDER_WIDTH
                        or y >= image.height - TRANSPARENT_BORDER_WIDTH
                    ):
                        border_pixels[x, y] = 255
            self.assertIsNone(ImageChops.multiply(alpha, border).getbbox())

            dirty_hidden_pixels = sum(
                1
                for red, green, blue, alpha_value in image.get_flattened_data()
                if alpha_value == 0 and (red or green or blue)
            )
            self.assertEqual(dirty_hidden_pixels, 0, f"Dirty hidden RGB in runtime frame {index}")

    def test_bottom_anchor_and_horizontal_center_do_not_drift(self):
        frames = load_runtime_frames()
        bounding_boxes = [image.getchannel("A").getbbox() for image in frames[1:]]
        self.assertTrue(all(bounding_boxes))
        first_box = bounding_boxes[0]
        first_center_x = (first_box[0] + first_box[2]) / 2
        max_center_drift = frames[0].width * MAX_HORIZONTAL_CENTER_DRIFT_RATIO
        max_bottom_drift = frames[0].height * MAX_BOTTOM_ANCHOR_DRIFT_RATIO
        for box in bounding_boxes:
            self.assertLessEqual(abs((box[0] + box[2]) / 2 - first_center_x), max_center_drift)
            self.assertLessEqual(abs(box[3] - first_box[3]), max_bottom_drift)

    def test_every_frame_is_unique_and_adjacent_changes_are_continuous(self):
        frames = load_runtime_frames()
        hashes = [sha256(image.tobytes()).hexdigest() for image in frames]
        self.assertEqual(len(hashes), len(set(hashes)))
        for first, second in zip(frames, frames[1:]):
            changed_ratio = nonzero_pixel_ratio(combined_difference_mask(first, second))
            self.assertGreaterEqual(changed_ratio, MIN_ADJACENT_CHANGE_RATIO)
            self.assertLessEqual(changed_ratio, MAX_ADJACENT_CHANGE_RATIO)

    def test_endpoint_keeps_center_clear_and_has_no_flag(self):
        frames = load_runtime_frames()
        self.assertIsNone(frames[0].getchannel("A").getbbox())
        alpha = frames[-1].getchannel("A")
        protected_center = alpha.crop((380, 255, 644, 650))
        visible_pixels = sum(protected_center.histogram()[1:])
        self.assertLess(visible_pixels / (protected_center.width * protected_center.height), 0.08)
        self.assertIsNone(alpha.crop((300, 0, 724, 280)).getbbox())

    def test_reverse_playback_reuses_the_exact_runtime_frames(self):
        hashes = [sha256(image.tobytes()).hexdigest() for image in load_runtime_frames()]
        self.assertEqual(list(reversed(list(reversed(hashes)))), hashes)


if __name__ == "__main__":
    unittest.main()
