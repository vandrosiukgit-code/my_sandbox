"""Shared debug drawing settings for layout rect overlays."""

DEBUG_RECTS = False

RECT_COLORS = (
    (255, 64, 64),
    (255, 160, 32),
    (255, 232, 64),
    (64, 220, 96),
    (64, 200, 255),
    (96, 128, 255),
    (192, 96, 255),
)


def get_rect_color(depth):
    return RECT_COLORS[int(depth) % len(RECT_COLORS)]
