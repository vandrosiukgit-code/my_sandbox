import json
import re
import unittest
from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageChops


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = PROJECT_ROOT / "assets" / "main_screen" / "player_attack"
FRAMES_DIR = ASSET_DIR / "frames"
ATTACK_REFERENCE_PATH = ASSET_DIR / "attack_overlay_reference.png"
SPRITE_SHEET_PATH = ASSET_DIR / "overlay.png"
RESOURCE_MANIFEST_PATH = PROJECT_ROOT / "assets" / "resource_manifest.json"

FRAME_NAME_PATTERN = re.compile(r"frame_(\d{2})\.png")
EXPECTED_FRAME_COUNT = 13
MIN_CANVAS_SIZE = (384, 320)
REFERENCE_PIXEL_TOLERANCE = 4
REFERENCE_CHANGED_PIXEL_RATIO = 0.005
MIN_ADJACENT_CHANGE_RATIO = 0.002
MAX_ADJACENT_CHANGE_RATIO = 0.60
MAX_HORIZONTAL_CENTER_DRIFT_RATIO = 0.03
MAX_BOTTOM_ANCHOR_DRIFT_RATIO = 0.02
TRANSPARENT_BORDER_WIDTH = 2


def discover_frame_paths():
    if not FRAMES_DIR.is_dir():
        return ()
    return tuple(sorted(FRAMES_DIR.glob("frame_*.png")))


def load_rgba(path):
    with Image.open(path) as image:
        image.load()
        return image.convert("RGBA")


def combined_difference_mask(first, second):
    difference = ImageChops.difference(first, second)
    mask = difference.getchannel("R")
    for channel_name in ("G", "B", "A"):
        mask = ImageChops.lighter(mask, difference.getchannel(channel_name))
    return mask


def nonzero_pixel_ratio(mask):
    histogram = mask.histogram()
    changed_pixels = sum(histogram[1:])
    return changed_pixels / (mask.width * mask.height)


class BottomPlayerAttackFrameAssetContractTests(unittest.TestCase):
    def require_frame_paths(self):
        paths = discover_frame_paths()
        if not paths:
            self.skipTest("Composite attack frames are not exported yet")
        return paths

    def require_reference_path(self):
        if not ATTACK_REFERENCE_PATH.is_file():
            self.skipTest("Attack overlay reference PNG is not exported yet")
        return ATTACK_REFERENCE_PATH

    def test_composite_frame_set_exists(self):
        self.assertTrue(
            FRAMES_DIR.is_dir(),
            "Expected attack-overlay PNG frames in assets/main_screen/player_attack/frames",
        )
        self.assertTrue(discover_frame_paths(), "No frame_XX.png files were found")

    def test_attack_overlay_reference_image_exists(self):
        self.assertTrue(
            ATTACK_REFERENCE_PATH.is_file(),
            "attack_overlay_reference.png must contain the approved transparent decoration",
        )

    def test_frame_names_are_contiguous_and_frame_count_is_reasonable(self):
        paths = self.require_frame_paths()
        indices = []
        for path in paths:
            match = FRAME_NAME_PATTERN.fullmatch(path.name)
            self.assertIsNotNone(match, f"Unexpected attack frame name: {path.name}")
            indices.append(int(match.group(1)))

        self.assertEqual(len(paths), EXPECTED_FRAME_COUNT)
        self.assertEqual(indices, list(range(len(paths))))

    def test_all_frames_are_rgba_png_files_on_one_canvas(self):
        paths = self.require_frame_paths()
        images = [load_rgba(path) for path in paths]
        expected_size = images[0].size

        self.assertGreaterEqual(expected_size[0], MIN_CANVAS_SIZE[0])
        self.assertGreaterEqual(expected_size[1], MIN_CANVAS_SIZE[1])
        for path, image in zip(paths, images):
            with Image.open(path) as source:
                self.assertEqual(source.format, "PNG")
                self.assertEqual(source.mode, "RGBA", f"{path.name} must have a native alpha channel")
            self.assertEqual(image.size, expected_size, f"Canvas mismatch in {path.name}")

    def test_frames_have_real_transparency_clean_hidden_rgb_and_no_clipped_edges(self):
        for index, path in enumerate(self.require_frame_paths()):
            image = load_rgba(path)
            alpha = image.getchannel("A")
            alpha_minimum, alpha_maximum = alpha.getextrema()
            self.assertEqual(alpha_minimum, 0, f"{path.name} has no transparent background")
            if index == 0:
                self.assertEqual(alpha_maximum, 0, "Idle overlay frame must be fully transparent")
            else:
                self.assertGreater(alpha_maximum, 0, f"{path.name} has no visible pixels")

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
            clipped_alpha = ImageChops.multiply(alpha, border)
            self.assertIsNone(clipped_alpha.getbbox(), f"Visible pixels touch the canvas edge in {path.name}")

            dirty_hidden_pixels = sum(
                1
                for red, green, blue, alpha_value in image.get_flattened_data()
                if alpha_value == 0 and (red or green or blue)
            )
            self.assertEqual(
                dirty_hidden_pixels,
                0,
                f"{path.name} contains RGB data under fully transparent pixels",
            )

    def test_bottom_anchor_and_horizontal_center_do_not_drift(self):
        images = [load_rgba(path) for path in self.require_frame_paths()]
        bounding_boxes = [image.getchannel("A").getbbox() for image in images[1:]]
        self.assertTrue(all(bounding_boxes), "Every non-idle frame must contain visible overlay pixels")

        first_box = bounding_boxes[0]
        first_center_x = (first_box[0] + first_box[2]) / 2
        max_center_drift = images[0].width * MAX_HORIZONTAL_CENTER_DRIFT_RATIO
        max_bottom_drift = images[0].height * MAX_BOTTOM_ANCHOR_DRIFT_RATIO

        for index, box in enumerate(bounding_boxes):
            center_x = (box[0] + box[2]) / 2
            self.assertLessEqual(
                abs(center_x - first_center_x),
                max_center_drift,
                f"Horizontal anchor drift in frame_{index:02d}.png",
            )
            self.assertLessEqual(
                abs(box[3] - first_box[3]),
                max_bottom_drift,
                f"Bottom anchor drift in frame_{index:02d}.png",
            )

    def test_every_frame_is_unique_and_adjacent_changes_are_continuous(self):
        paths = self.require_frame_paths()
        images = [load_rgba(path) for path in paths]
        hashes = [sha256(image.tobytes()).hexdigest() for image in images]
        self.assertEqual(len(hashes), len(set(hashes)), "Duplicate frames add a visible pause")

        for index, (first, second) in enumerate(zip(images, images[1:])):
            changed_ratio = nonzero_pixel_ratio(combined_difference_mask(first, second))
            self.assertGreaterEqual(
                changed_ratio,
                MIN_ADJACENT_CHANGE_RATIO,
                f"Frames {index:02d} and {index + 1:02d} barely change",
            )
            self.assertLessEqual(
                changed_ratio,
                MAX_ADJACENT_CHANGE_RATIO,
                f"Frames {index:02d} and {index + 1:02d} jump too sharply",
            )

    def test_first_frame_is_empty_and_last_matches_approved_reference(self):
        paths = self.require_frame_paths()
        self.assertIsNone(load_rgba(paths[0]).getchannel("A").getbbox())
        frame = load_rgba(paths[-1])
        reference = load_rgba(self.require_reference_path())
        self.assertEqual(frame.size, reference.size, "Attack reference canvas mismatch")
        difference_mask = combined_difference_mask(frame, reference)
        excessive_difference = difference_mask.point(
            lambda value: 255 if value > REFERENCE_PIXEL_TOLERANCE else 0
        )
        self.assertLessEqual(
            nonzero_pixel_ratio(excessive_difference),
            REFERENCE_CHANGED_PIXEL_RATIO,
            "The final frame does not match its approved overlay reference",
        )

    def test_overlay_keeps_the_portrait_and_real_hand_center_clear(self):
        image = load_rgba(self.require_reference_path())
        protected_center = image.getchannel("A").crop((380, 255, 644, 650))
        visible_pixels = sum(protected_center.histogram()[1:])
        self.assertLess(
            visible_pixels / (protected_center.width * protected_center.height),
            0.08,
            "Overlay fills the center where the real portrait and hand must remain visible",
        )

    def test_overlay_has_no_flag_or_flagpole_in_the_upper_region(self):
        image = load_rgba(self.require_reference_path())
        former_flag_region = image.getchannel("A").crop((300, 0, 724, 280))

        self.assertIsNone(
            former_flag_region.getbbox(),
            "The upper overlay region must stay empty after removing the flag",
        )

    def test_sprite_sheet_and_manifest_match_exported_frames(self):
        paths = self.require_frame_paths()
        frames = [load_rgba(path) for path in paths]
        sheet = load_rgba(SPRITE_SHEET_PATH)
        self.assertEqual(sheet.size, (frames[0].width, frames[0].height * len(frames)))
        for index, frame in enumerate(frames):
            crop = sheet.crop((0, index * frame.height, frame.width, (index + 1) * frame.height))
            self.assertIsNone(ImageChops.difference(crop, frame).getbbox())

        manifest = json.loads(RESOURCE_MANIFEST_PATH.read_text(encoding="utf-8"))["resources"]
        resource = manifest["main_screen.player_attack.overlay"]
        self.assertEqual(resource["path"], "main_screen/player_attack/overlay.png")
        self.assertEqual((resource["frame_width"], resource["frame_height"]), frames[0].size)

    def test_reverse_playback_uses_the_exact_forward_frames(self):
        paths = self.require_frame_paths()
        forward_hashes = [sha256(load_rgba(path).tobytes()).hexdigest() for path in paths]
        reverse_hashes = list(reversed(forward_hashes))

        self.assertEqual(list(reversed(reverse_hashes)), forward_hashes)
        self.assertFalse(tuple(FRAMES_DIR.glob("reverse_*.png")), "Do not maintain a second reverse frame set")


if __name__ == "__main__":
    unittest.main()
