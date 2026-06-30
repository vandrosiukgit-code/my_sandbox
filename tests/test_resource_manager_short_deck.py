import unittest

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


if __name__ == "__main__":
    unittest.main()
