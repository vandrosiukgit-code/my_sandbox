"""Helpers for visual card conceal/reveal surface handling."""

import pygame


def create_transparent_surface_like(surface):
    return pygame.Surface(surface.get_size(), pygame.SRCALPHA)


def create_transparent_surface_for_frames(frames):
    if not frames:
        return None
    return create_transparent_surface_like(frames[0])


def apply_transparent_primary_surface(group, frames):
    surface = create_transparent_surface_for_frames(frames)
    if surface is None:
        return False
    group.set_primary_layer_frames([surface], position=(0, 0))
    return True


def restore_primary_frames(group, frames):
    if not frames:
        return False
    group.set_primary_layer_frames([frame.copy() for frame in frames], position=(0, 0))
    return True
