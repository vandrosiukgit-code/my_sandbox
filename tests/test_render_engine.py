import os
import unittest

from core.render_engine import RenderEngine


class RenderEngineWindowPositionTests(unittest.TestCase):
    def test_apply_window_position_defaults_enables_centering_when_position_not_forced(self):
        original_centered = os.environ.get("SDL_VIDEO_CENTERED")
        original_position = os.environ.get("SDL_VIDEO_WINDOW_POS")
        try:
            os.environ.pop("SDL_VIDEO_CENTERED", None)
            os.environ.pop("SDL_VIDEO_WINDOW_POS", None)

            RenderEngine._apply_window_position_defaults()

            self.assertEqual(os.environ.get("SDL_VIDEO_CENTERED"), "1")
        finally:
            if original_centered is None:
                os.environ.pop("SDL_VIDEO_CENTERED", None)
            else:
                os.environ["SDL_VIDEO_CENTERED"] = original_centered
            if original_position is None:
                os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
            else:
                os.environ["SDL_VIDEO_WINDOW_POS"] = original_position

    def test_apply_window_position_defaults_respects_explicit_window_position(self):
        original_centered = os.environ.get("SDL_VIDEO_CENTERED")
        original_position = os.environ.get("SDL_VIDEO_WINDOW_POS")
        try:
            os.environ["SDL_VIDEO_WINDOW_POS"] = "10,20"
            os.environ.pop("SDL_VIDEO_CENTERED", None)

            RenderEngine._apply_window_position_defaults()

            self.assertNotIn("SDL_VIDEO_CENTERED", os.environ)
        finally:
            if original_centered is None:
                os.environ.pop("SDL_VIDEO_CENTERED", None)
            else:
                os.environ["SDL_VIDEO_CENTERED"] = original_centered
            if original_position is None:
                os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
            else:
                os.environ["SDL_VIDEO_WINDOW_POS"] = original_position


if __name__ == "__main__":
    unittest.main()
