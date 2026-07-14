import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.resource import ResourceManager


class ResourceManagerShortDeckTests(unittest.TestCase):
    def test_prune_manifest_for_short_deck_removes_cards_below_six_and_jokers(self):
        manifest = {
            "resources": {
                "cards.2_of_clubs": {"path": "cards/2_of_clubs.png", "frame_width": 1, "frame_height": 1},
                "cards.5_of_hearts": {"path": "cards/5_of_hearts.png", "frame_width": 1, "frame_height": 1},
                "cards.6_of_spades": {"path": "cards/6_of_spades.png", "frame_width": 1, "frame_height": 1},
                "cards.a_of_hearts": {"path": "cards/a_of_hearts.png", "frame_width": 1, "frame_height": 1},
                "cards.black_joker": {"path": "cards/black_joker.png", "frame_width": 1, "frame_height": 1},
                "cards.card_back": {"path": "cards/card_back.png", "frame_width": 1, "frame_height": 1},
            }
        }

        pruned, changed = ResourceManager.prune_manifest_for_short_deck(manifest)

        self.assertTrue(changed)
        self.assertEqual(
            set(pruned["resources"]),
            {"cards.6_of_spades", "cards.a_of_hearts", "cards.card_back"},
        )

    def test_build_index_removes_missing_manifest_entries(self):
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir)
            manifest = {
                "resources": {
                    "test.missing": {
                        "path": "test/missing.png",
                        "frame_width": 10,
                        "frame_height": 10,
                    }
                }
            }
            ResourceManager.save_manifest(str(assets_dir), manifest)

            runtime_index = ResourceManager.build_index(str(assets_dir))
            saved_manifest = ResourceManager.load_manifest(str(assets_dir))

        self.assertEqual(runtime_index, {})
        self.assertEqual(saved_manifest["resources"], {})


if __name__ == "__main__":
    unittest.main()
