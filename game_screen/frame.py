"""РђРєС‚РёРІРЅР°СЏ СЌРєСЂР°РЅРЅР°СЏ Р·РѕРЅР°.

Frame - СЌС‚Рѕ СЌРєСЂР°РЅРЅС‹Р№ РєРѕРЅС‚РµР№РЅРµСЂ РґР»СЏ Group-РѕРІ. РћРЅР° РЅРµ Р·РЅР°РµС‚ РїСЂР°РІРёР»
РёРіСЂС‹ Рё РЅРµ СЂРµС€Р°РµС‚, РїРѕС‡РµРјСѓ РєР°СЂС‚Р° РЅР°С…РѕРґРёС‚СЃСЏ РІ СЂСѓРєРµ РёР»Рё РЅР° СЃС‚РѕР»Рµ. РћРЅР° РѕС‚РІРµС‡Р°РµС‚
С‚РѕР»СЊРєРѕ Р·Р° СЌРєСЂР°РЅРЅСѓСЋ РіРµРѕРјРµС‚СЂРёСЋ: РіРґРµ Р·РѕРЅР° СЂР°СЃРїРѕР»РѕР¶РµРЅР°, РєР°РєРёРµ group ID СЃРµР№С‡Р°СЃ
РѕС‚РЅРѕСЃСЏС‚СЃСЏ Рє Р·РѕРЅРµ Рё РєР°Рє РїРѕСЃС‚Р°РІРёС‚СЊ СЌС‚Рё group-С‹ РІРЅСѓС‚СЂРё СЃРІРѕРµРіРѕ rect.
"""

import pygame

from base import BaseFrame
from game_screen.events import FrameHit


class Frame(BaseFrame):
    """Р­РєСЂР°РЅРЅР°СЏ Р·РѕРЅР°, РєРѕС‚РѕСЂР°СЏ СЂР°Р·РјРµС‰Р°РµС‚ group-С‹ РІРЅСѓС‚СЂРё СЃРІРѕРµРіРѕ rect."""

    def __init__(
        self,
        frame_id,
        rect,
        hit_rect=None,
        group_ids=None,
        padding=0,
        spacing=12,
        parent_frame=None,
    ):
        """РЎРѕР·РґР°С‚СЊ Р°РєС‚РёРІРЅСѓСЋ СЌРєСЂР°РЅРЅСѓСЋ Р·РѕРЅСѓ.

        Args:
            frame_id: РЎС‚Р°Р±РёР»СЊРЅС‹Р№ ID Р·РѕРЅС‹, РЅР°РїСЂРёРјРµСЂ "bottom_hand".
            rect: РџРѕР·РёС†РёСЏ Рё СЂР°Р·РјРµСЂ Р·РѕРЅС‹ РІ РєРѕРѕСЂРґРёРЅР°С‚Р°С… СЌРєСЂР°РЅР°.
            hit_rect: РћР±Р»Р°СЃС‚СЊ РєР»РёРєР°/РІР·Р°РёРјРѕРґРµР№СЃС‚РІРёСЏ. Р•СЃР»Рё РЅРµ Р·Р°РґР°РЅР°, СЂР°РІРЅР° rect.
            group_ids: РќР°С‡Р°Р»СЊРЅС‹Р№ СЃРїРёСЃРѕРє group ID РІРЅСѓС‚СЂРё Р·РѕРЅС‹.
            padding: Р’РЅСѓС‚СЂРµРЅРЅРёР№ РѕС‚СЃС‚СѓРї РґР»СЏ Р±Р°Р·РѕРІРѕР№ СЂР°СЃРєР»Р°РґРєРё.
            spacing: Р Р°СЃСЃС‚РѕСЏРЅРёРµ РјРµР¶РґСѓ group-Р°РјРё РІ Р±Р°Р·РѕРІРѕР№ СЂР°СЃРєР»Р°РґРєРµ.
        """
        self.frame_id = frame_id
        self._rect = pygame.Rect(rect)
        self._hit_rect = pygame.Rect(hit_rect) if hit_rect is not None else self._rect.copy()
        self.parent_frame = parent_frame
        self.child_frames = {}
        self.group_ids = list(group_ids or [])
        self.padding = padding
        self.spacing = spacing
        self.group_origins = {}
        self.actions = []

    @property
    def id(self):
        """РЎС‚Р°Р±РёР»СЊРЅС‹Р№ ID СЌРєСЂР°РЅРЅРѕР№ Р·РѕРЅС‹."""
        return self.frame_id

    @property
    def rect(self):
        """РџСЂСЏРјРѕСѓРіРѕР»СЊРЅРёРє Р·РѕРЅС‹ РІ РєРѕРѕСЂРґРёРЅР°С‚Р°С… СЌРєСЂР°РЅР°."""
        return self._to_screen_rect(self._rect)

    @property
    def hit_rect(self):
        """РћР±Р»Р°СЃС‚СЊ РІР·Р°РёРјРѕРґРµР№СЃС‚РІРёСЏ Р·РѕРЅС‹ РІ РєРѕРѕСЂРґРёРЅР°С‚Р°С… СЌРєСЂР°РЅР°."""
        return self._to_screen_rect(self._hit_rect)

    @property
    def local_rect(self):
        """Rectangle in the parent frame coordinate system."""
        return self._rect

    def add_child_frame(self, frame):
        """Attach a child frame to this frame."""
        if frame.id in self.child_frames:
            raise ValueError(f"Child Frame already exists: {frame.id}")
        frame.parent_frame = self
        self.child_frames[frame.id] = frame
        return frame

    def get_child_frame(self, frame_id):
        """Return a direct child frame by ID."""
        return self.child_frames[frame_id]

    def set_local_position(self, x, y):
        """Move this frame inside its parent coordinate system."""
        old_position = self._rect.topleft
        self._rect.topleft = (int(x), int(y))
        self._hit_rect.move_ip(
            self._rect.x - old_position[0],
            self._rect.y - old_position[1],
        )

    def set_group_ids(self, group_ids):
        """Р—Р°РґР°С‚СЊ РїРѕР»РЅС‹Р№ СЃРїРёСЃРѕРє group ID РІ Р·РѕРЅРµ.

        Р­С‚РѕС‚ РјРµС‚РѕРґ СѓРґРѕР±РµРЅ, РєРѕРіРґР° GameScreen С‡РёС‚Р°РµС‚ fixture РёР· GameController:
        РѕРЅ Р±РµСЂРµС‚ СЃРїРёСЃРѕРє card_id РёР· Р»РѕРіРёС‡РµСЃРєРѕР№ Р·РѕРЅС‹ Рё РїРµСЂРµРґР°РµС‚ РµРіРѕ СЃСЋРґР°.
        """
        self.group_ids = list(group_ids)

    def add_group_id(self, group_id):
        """Р”РѕР±Р°РІРёС‚СЊ group ID РІ Р·РѕРЅСѓ Р±РµР· РґСѓР±Р»РµР№."""
        if group_id not in self.group_ids:
            self.group_ids.append(group_id)

    def remove_group_id(self, group_id):
        """РЈР±СЂР°С‚СЊ group ID РёР· Р·РѕРЅС‹, РµСЃР»Рё РѕРЅ С‚Р°Рј РµСЃС‚СЊ."""
        if group_id in self.group_ids:
            self.group_ids.remove(group_id)

    def calculate_group_position(self, index, group_count, group=None):
        """Р Р°СЃСЃС‡РёС‚Р°С‚СЊ РїРѕР·РёС†РёСЋ group-Р° РІРЅСѓС‚СЂРё Р·РѕРЅС‹.

        РЎРµР№С‡Р°СЃ СЌС‚Рѕ РїСЂРѕСЃС‚Р°СЏ РіРѕСЂРёР·РѕРЅС‚Р°Р»СЊРЅР°СЏ СЂР°СЃРєР»Р°РґРєР° СЃР»РµРІР° РЅР°РїСЂР°РІРѕ. РћРЅР° РЅСѓР¶РЅР°
        РєР°Рє Р±РµР·РѕРїР°СЃРЅР°СЏ Р·Р°РіРѕС‚РѕРІРєР°. РџРѕР·Р¶Рµ Р·РґРµСЃСЊ РјРѕР¶РЅРѕ Р·Р°РјРµРЅРёС‚СЊ Р°Р»РіРѕСЂРёС‚Рј РЅР° РІРµРµСЂ,
        С†РµРЅС‚СЂРёСЂРѕРІР°РЅРёРµ, СЃС‚РѕРїРєСѓ РєРѕР»РѕРґС‹ РёР»Рё Р»СЋР±СѓСЋ РґСЂСѓРіСѓСЋ СЃС…РµРјСѓ.
        """
        return self.to_screen(self.calculate_group_local_position(index, group_count, group))

    def calculate_group_local_position(self, index, group_count, group=None):
        """Return group position in the frame local coordinate system."""
        _ = group_count
        x = self.padding + index * self.get_group_step(group)
        y = self.padding
        return x, y

    def apply_layout(self, group_store):
        """РџРѕСЃС‚Р°РІРёС‚СЊ group-С‹ РёР· group_store РЅР° РїРѕР·РёС†РёРё РІРЅСѓС‚СЂРё Р·РѕРЅС‹.

        Frame СЂР°Р±РѕС‚Р°РµС‚ С‚РѕР»СЊРєРѕ СЃ ID. РЎР°РјРё Group РѕРЅР° РїРѕР»СѓС‡Р°РµС‚ С‡РµСЂРµР·
        group_store, РїРѕСЌС‚РѕРјСѓ РЅРµ СЃС‚Р°РЅРѕРІРёС‚СЃСЏ РІР»Р°РґРµР»СЊС†РµРј РіСЂР°С„РёС‡РµСЃРєРёС… РѕР±СЉРµРєС‚РѕРІ.
        """
        group_count = len(self.group_ids)
        for index, group_id in enumerate(self.group_ids):
            group = group_store.get(group_id)
            position = self.calculate_group_position(index, group_count, group)
            group.set_position(*position)
            self.group_origins[group_id] = position

    def add_action(self, action):
        """Add a visual Action owned by this frame."""
        self.actions.append(action)
        if hasattr(action, "start"):
            action.start()
        return action

    def update_actions(self, dt):
        """Update active visual Actions and drop finished ones."""
        for frame in self.child_frames.values():
            frame.update_actions(dt)

        running_actions = []
        for action in self.actions:
            action.update(dt)
            if not self.is_action_finished(action):
                running_actions.append(action)
        self.actions = running_actions

    @staticmethod
    def is_action_finished(action):
        is_finished = getattr(action, "is_finished", False)
        if callable(is_finished):
            return is_finished()
        return bool(is_finished)

    def to_local(self, screen_pos):
        """Convert screen coordinates to this frame local coordinates."""
        rect = self.rect
        return (int(screen_pos[0] - rect.x), int(screen_pos[1] - rect.y))

    def to_screen(self, local_pos):
        """Convert local frame coordinates to screen coordinates."""
        if self.parent_frame is None:
            return (int(self._rect.x + local_pos[0]), int(self._rect.y + local_pos[1]))

        parent_local_pos = (
            self._rect.x + local_pos[0],
            self._rect.y + local_pos[1],
        )
        return self.parent_frame.to_screen(parent_local_pos)

    def hit_test(self, screen_pos, group_store):
        """Return FrameHit for the topmost group under screen_pos inside this frame."""
        if not self.contains_point(screen_pos):
            return None

        local_pos = self.to_local(screen_pos)
        for frame in reversed(tuple(self.child_frames.values())):
            hit = frame.hit_test(screen_pos, group_store)
            if hit is not None:
                return hit

        for group_id in reversed(self.group_ids):
            group = group_store.get(group_id)
            if group.hit_rect.collidepoint(screen_pos):
                return FrameHit(
                    frame_id=self.id,
                    group_id=group_id,
                    screen_pos=tuple(screen_pos),
                    local_pos=local_pos,
                )

        return FrameHit(
            frame_id=self.id,
            group_id=None,
            screen_pos=tuple(screen_pos),
            local_pos=local_pos,
        )

    def get_group_origin(self, group_id):
        """Р’РµСЂРЅСѓС‚СЊ РїРѕСЃР»РµРґРЅСЋСЋ СЂР°СЃСЃС‡РёС‚Р°РЅРЅСѓСЋ СЌРєСЂР°РЅРЅСѓСЋ С‚РѕС‡РєСѓ group-Р°."""
        return self.group_origins.get(group_id, self.rect.topleft)

    def contains_point(self, point):
        """РџСЂРѕРІРµСЂРёС‚СЊ РїРѕРїР°РґР°РЅРёРµ С‚РѕС‡РєРё РІ hit_rect Р·РѕРЅС‹."""
        return self.hit_rect.collidepoint(point)

    def get_group_step(self, group):
        """Р’РµСЂРЅСѓС‚СЊ С€Р°Рі РјРµР¶РґСѓ group-Р°РјРё РґР»СЏ Р±Р°Р·РѕРІРѕР№ СЂР°СЃРєР»Р°РґРєРё.

        Р•СЃР»Рё group СѓР¶Рµ РёРјРµРµС‚ rect, С€Р°Рі СЂР°РІРµРЅ РµРіРѕ С€РёСЂРёРЅРµ РїР»СЋСЃ spacing. Р•СЃР»Рё
        group РЅРµ РїРµСЂРµРґР°РЅ, РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ С‚РѕР»СЊРєРѕ spacing. Р­С‚Рѕ РїРѕР·РІРѕР»СЏРµС‚ РјРµС‚РѕРґСѓ
        СЂР°Р±РѕС‚Р°С‚СЊ Рё РІ СЂР°РЅРЅРёС… С‡РµСЂРЅРѕРІС‹С… СЃС†РµРЅР°СЂРёСЏС….
        """
        if group is None:
            return self.spacing
        return group.rect.width + self.spacing

    def to_payload(self):
        """Р’РµСЂРЅСѓС‚СЊ СЃР»РѕРІР°СЂСЊ СЃ РїР°СЂР°РјРµС‚СЂР°РјРё Р·РѕРЅС‹ РґР»СЏ РѕС‚Р»Р°РґРєРё Рё РґРѕРєСѓРјРµРЅС‚Р°С†РёРё."""
        return {
            "frame_id": self.id,
            "parent_frame_id": self.parent_frame.id if self.parent_frame is not None else None,
            "local_rect": tuple(self.local_rect),
            "rect": tuple(self.rect),
            "hit_rect": tuple(self.hit_rect),
            "group_ids": tuple(self.group_ids),
            "child_frame_ids": tuple(self.child_frames),
            "group_origins": dict(self.group_origins),
            "action_count": len(self.actions),
            "padding": self.padding,
            "spacing": self.spacing,
        }

    def _to_screen_rect(self, rect):
        """Convert a rect from parent-frame coordinates to screen coordinates."""
        screen_pos = self.to_screen((rect.x - self._rect.x, rect.y - self._rect.y))
        return pygame.Rect(screen_pos, rect.size)


