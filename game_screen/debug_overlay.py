"""Shared debug drawing settings for layout rect overlays."""

DEBUG_RECTS = False
FRAME_RECTS = True
GROUP_RECTS = False
ACTIVITY_RECTS = False
FRAME_DEPTHS = None
FRAME_IDS = None
FRAME_ID_PREFIXES = None

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


def configure(fixture):
    """Apply debug overlay fixture values."""
    global DEBUG_RECTS
    global FRAME_RECTS
    global GROUP_RECTS
    global ACTIVITY_RECTS
    global FRAME_DEPTHS
    global FRAME_IDS
    global FRAME_ID_PREFIXES

    if not fixture:
        return

    if "enabled" in fixture:
        DEBUG_RECTS = bool(fixture["enabled"])
    if "frames" in fixture:
        FRAME_RECTS = bool(fixture["frames"])
    if "groups" in fixture:
        GROUP_RECTS = bool(fixture["groups"])
    if "activities" in fixture:
        ACTIVITY_RECTS = bool(fixture["activities"])
    if "frame_depths" in fixture:
        FRAME_DEPTHS = normalize_optional_set(fixture["frame_depths"], int)
    if "frame_ids" in fixture:
        FRAME_IDS = normalize_optional_set(fixture["frame_ids"], str)
    if "frame_id_prefixes" in fixture:
        FRAME_ID_PREFIXES = normalize_optional_set(fixture["frame_id_prefixes"], str)


def normalize_optional_set(value, item_type):
    if value is None:
        return None
    if isinstance(value, (str, int)):
        return frozenset((item_type(value),))
    return frozenset(item_type(item) for item in value)


def should_draw_frame_rect(frame, depth):
    if not FRAME_RECTS:
        return False
    if FRAME_DEPTHS is not None and int(depth) not in FRAME_DEPTHS:
        return False
    frame_id = getattr(frame, "id", None)
    if FRAME_IDS is not None and frame_id not in FRAME_IDS:
        return False
    if FRAME_ID_PREFIXES is not None and not any(
        str(frame_id).startswith(prefix)
        for prefix in FRAME_ID_PREFIXES
    ):
        return False
    return DEBUG_RECTS or not getattr(frame, "hide_rect", True)


def should_draw_group_rect(group):
    if not GROUP_RECTS:
        return False
    return DEBUG_RECTS or not getattr(group, "hide_rect", True)


def should_draw_activity_rect():
    return ACTIVITY_RECTS and DEBUG_RECTS
