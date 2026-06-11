"""Shared easing and interpolation helpers for visual animations."""


def clamp01(value):
    return max(0.0, min(1.0, float(value)))


def ease_out_quad(progress):
    progress = clamp01(progress)
    return 1.0 - (1.0 - progress) * (1.0 - progress)


def lerp_float(start, end, progress):
    progress = clamp01(progress)
    return float(start) + (float(end) - float(start)) * progress


def lerp_int(start, end, progress):
    return int(round(lerp_float(start, end, progress)))
