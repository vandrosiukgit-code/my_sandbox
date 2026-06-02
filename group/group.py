"""РџР°СЃСЃРёРІРЅС‹Р№ GUI group РїСЂРѕРµРєС‚Р° The Fool's Reef.

Group - СЌС‚Рѕ РїСЂРѕСЃС‚РѕР№ РІРёР·СѓР°Р»СЊРЅС‹Р№ РєРёСЂРїРёС‡РёРє. РћРЅ РЅРµ Р·РЅР°РµС‚ РїСЂР°РІРёР» РёРіСЂС‹, РЅРµ
Р·Р°РіСЂСѓР¶Р°РµС‚ PNG СЃР°Рј Рё РЅРµ СЃРѕРґРµСЂР¶РёС‚ Р»РѕРєР°Р»СЊРЅРѕР№ СЂР°СЃРєР»Р°РґРєРё СЃР»РѕРµРІ. Р’СЃРµ РµРіРѕ СЃР»РѕРё
СЂРёСЃСѓСЋС‚СЃСЏ РёР· РѕРґРЅРѕР№ Р±Р°Р·РѕРІРѕР№ С‚РѕС‡РєРё group.rect.topleft.
"""

from dataclasses import dataclass

import pygame

from base import BaseGroup


@dataclass
class Layer:
    """РћРґРёРЅ РіСЂР°С„РёС‡РµСЃРєРёР№ СЃР»РѕР№ Group.

    РЎР»РѕР№ С…СЂР°РЅРёС‚ С‚РѕР»СЊРєРѕ РёРјСЏ, СЃРїРёСЃРѕРє РєР°РґСЂРѕРІ Рё РёРЅРґРµРєСЃ С‚РµРєСѓС‰РµРіРѕ РєР°РґСЂР°. РЈ СЃР»РѕСЏ
    СЃРѕР·РЅР°С‚РµР»СЊРЅРѕ РЅРµС‚ offset, visible Рё alpha: СЌС‚Рѕ Р°СЂС…РёС‚РµРєС‚СѓСЂРЅРѕРµ РѕРіСЂР°РЅРёС‡РµРЅРёРµ,
    С‡С‚РѕР±С‹ group РЅРµ РїСЂРµРІСЂР°С‰Р°Р»СЃСЏ РІ РјРёРЅРё-СЃС†РµРЅСѓ.
    """

    name: str
    frames: list
    current_frame_index: int = 0

    def get_current_frame(self):
        """Р’РµСЂРЅСѓС‚СЊ С‚РµРєСѓС‰РёР№ pygame.Surface СЃР»РѕСЏ."""
        if not self.frames:
            return None
        return self.frames[self.current_frame_index]

    def set_frame(self, frame_index):
        """Р’С‹Р±СЂР°С‚СЊ С‚РµРєСѓС‰РёР№ РєР°РґСЂ СЃР»РѕСЏ СЃ Р·Р°С‰РёС‚РѕР№ РѕС‚ РІС‹С…РѕРґР° Р·Р° РіСЂР°РЅРёС†С‹."""
        if not self.frames:
            self.current_frame_index = 0
            return
        self.current_frame_index = max(0, min(int(frame_index), len(self.frames) - 1))


class Group(BaseGroup):
    """РџР°СЃСЃРёРІРЅС‹Р№ drawable-РѕР±СЉРµРєС‚ СЃ rect, hit_rect, scale_factor Рё СЃР»РѕСЏРјРё РєР°РґСЂРѕРІ.

    Group РЅРµ СЂР°Р·Р»РёС‡Р°РµС‚ СЃС‚Р°С‚РёРєСѓ Рё Р°РЅРёРјР°С†РёСЋ. Р›СЋР±РѕР№ PNG РїРѕСЃР»Рµ ResourceManager
    СЃС‚Р°РЅРѕРІРёС‚СЃСЏ СЃРїРёСЃРєРѕРј РєР°РґСЂРѕРІ: РѕР±С‹С‡РЅР°СЏ РєР°СЂС‚РёРЅРєР° - СЌС‚Рѕ СЃРїРёСЃРѕРє РёР· РѕРґРЅРѕРіРѕ РєР°РґСЂР°,
    spritesheet - СЃРїРёСЃРѕРє РёР· РЅРµСЃРєРѕР»СЊРєРёС… РєР°РґСЂРѕРІ. Activity РјРѕР¶РµС‚ РјРµРЅСЏС‚СЊ С‚РµРєСѓС‰РёР№
    РєР°РґСЂ СЃР»РѕСЏ, РїРѕР·РёС†РёСЋ group-Р° Рё scale_factor, РЅРѕ РЅРµ РїСЂР°РІРёР»Р° РёРіСЂС‹.
    """

    def __init__(self, group_id, rect=(0, 0, 0, 0), layers=None, scale_factor=1.0):
        """РЎРѕР·РґР°С‚СЊ Group РёР· РіРѕС‚РѕРІС‹С… СЃРїРёСЃРєРѕРІ РєР°РґСЂРѕРІ.

        Args:
            group_id: РЎС‚Р°Р±РёР»СЊРЅС‹Р№ ID, РѕР±С‰РёР№ РґР»СЏ РІРёР·СѓР°Р»СЊРЅРѕРіРѕ СЃР»РѕСЏ Рё Р»РѕРіРёРєРё.
            rect: Р‘Р°Р·РѕРІС‹Р№ РїСЂСЏРјРѕСѓРіРѕР»СЊРЅРёРє group-Р° РЅР° СЌРєСЂР°РЅРµ.
            layers: РЎР»РѕРё РІ РїРѕСЂСЏРґРєРµ РѕС‚СЂРёСЃРѕРІРєРё.
            scale_factor: РњР°СЃС€С‚Р°Р± РІСЃРµРіРѕ group-Р°. РњР°СЃС€С‚Р°Р±РёСЂСѓСЋС‚СЃСЏ rect, hit_rect Рё
                РІСЃРµ РєР°РґСЂС‹ РїСЂРё РѕС‚СЂРёСЃРѕРІРєРµ, РЅРѕ РёСЃС…РѕРґРЅС‹Рµ Surface РЅРµ РјРµРЅСЏСЋС‚СЃСЏ.
        """
        if not group_id:
            raise ValueError("Group С‚СЂРµР±СѓРµС‚ РЅРµРїСѓСЃС‚РѕР№ group_id")

        self.group_id = group_id
        self._base_rect = pygame.Rect(rect)
        self._rect = self._base_rect.copy()
        self._base_hit_rect = self._base_rect.copy()
        self._hit_rect = self._base_hit_rect.copy()
        self.scale_factor = float(scale_factor)
        self.layers = []

        for layer in layers or []:
            self.add_layer(layer)

        if self._base_rect.size == (0, 0):
            self.refresh_rect_from_layers()
        self.apply_scale()

    @classmethod
    def create_group(cls, group_id, graphics, rect=(0, 0, 0, 0), resource_manager=None):
        """РЎРѕР±СЂР°С‚СЊ Group РїРѕ РѕРїРёСЃР°РЅРёСЋ СЃР»РѕРµРІ Рё РєР»СЋС‡Р°Рј ResourceManager.

        Р­С‚Рѕ СѓРґРѕР±РЅР°СЏ С‚РѕС‡РєР° СЃР±РѕСЂРєРё, Р° РЅРµ РѕС‚РґРµР»СЊРЅР°СЏ С„Р°Р±СЂРёРєР°. РљР°Р¶РґС‹Р№ СЌР»РµРјРµРЅС‚ graphics
        Р·Р°РґР°РµС‚ СЃР»РѕР№ РІ РїРѕСЂСЏРґРєРµ РѕС‚СЂРёСЃРѕРІРєРё:

        - ("layer_name", "resource.key")
        - {"name": "layer_name", "resource_key": "resource.key"}

        ResourceManager РїРµСЂРµРґР°РµС‚СЃСЏ СЃРЅР°СЂСѓР¶Рё Рё РІСЃРµРіРґР° РѕС‚РґР°РµС‚ СЃРїРёСЃРѕРє РєР°РґСЂРѕРІ С‡РµСЂРµР·
        get_frames(). РўР°Рє Group РЅРµ РёРјРїРѕСЂС‚РёСЂСѓРµС‚ СЂРµСЃСѓСЂСЃРЅС‹Р№ СЃР»РѕР№ РЅР°РїСЂСЏРјСѓСЋ.
        """
        if resource_manager is None:
            raise ValueError("Group.create_group() С‚СЂРµР±СѓРµС‚ resource_manager СЃ РјРµС‚РѕРґРѕРј get_frames()")

        layers = []
        for graphic in graphics:
            layer_name, resource_key = cls.normalize_graphic(graphic)
            layers.append(Layer(layer_name, resource_manager.get_frames(resource_key)))
        return cls(group_id=group_id, rect=rect, layers=layers)

    @staticmethod
    def normalize_graphic(graphic):
        """РџСЂРёРІРµСЃС‚Рё РѕРїРёСЃР°РЅРёРµ СЃР»РѕСЏ Рє РїР°СЂРµ layer_name/resource_key."""
        if isinstance(graphic, dict):
            layer_name = graphic.get("name") or graphic.get("layer_name")
            resource_key = graphic.get("resource_key")
            if not layer_name or not resource_key:
                raise ValueError(f"РЈ СЃР»РѕСЏ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ name Рё resource_key: {graphic!r}")
            return layer_name, resource_key

        if isinstance(graphic, (tuple, list)) and len(graphic) >= 2:
            return graphic[0], graphic[1]

        raise TypeError(
            "РЎР»РѕР№ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РѕРїРёСЃР°РЅ РєР°Рє (layer_name, resource_key) "
            "РёР»Рё {'name': ..., 'resource_key': ...}"
        )

    @property
    def id(self):
        """РЎС‚Р°Р±РёР»СЊРЅС‹Р№ ID group-Р°."""
        return self.group_id

    @property
    def rect(self):
        """РўРµРєСѓС‰РёР№ РїСЂСЏРјРѕСѓРіРѕР»СЊРЅРёРє group-Р° РЅР° СЌРєСЂР°РЅРµ СЃ СѓС‡РµС‚РѕРј scale_factor."""
        return self._rect

    @property
    def hit_rect(self):
        """РћР±СЏР·Р°С‚РµР»СЊРЅР°СЏ РѕР±Р»Р°СЃС‚СЊ РІР·Р°РёРјРѕРґРµР№СЃС‚РІРёСЏ group-Р° СЃ СѓС‡РµС‚РѕРј scale_factor."""
        return self._hit_rect

    def update(self, dt):
        """РћР±РЅРѕРІРёС‚СЊ group.

        РњРµС‚РѕРґ РЅР°РјРµСЂРµРЅРЅРѕ РїСѓСЃС‚РѕР№: Group РЅРµ РїСЂРѕРёРіСЂС‹РІР°РµС‚ Р°РЅРёРјР°С†РёСЋ СЃР°Рј. Р’СЂРµРјРµРЅРЅСѓСЋ
        СЃРјРµРЅСѓ РєР°РґСЂРѕРІ, РїРµСЂРµРјРµС‰РµРЅРёРµ Рё РјР°СЃС€С‚Р°Р±РёСЂРѕРІР°РЅРёРµ РІС‹РїРѕР»РЅСЏСЋС‚ Activity РёР»Рё СЌРєСЂР°РЅ.
        """
        _ = dt

    def draw(self, screen):
        """РћС‚СЂРёСЃРѕРІР°С‚СЊ С‚РµРєСѓС‰РёР№ РєР°РґСЂ РєР°Р¶РґРѕРіРѕ СЃР»РѕСЏ РІ Р±Р°Р·РѕРІРѕР№ С‚РѕС‡РєРµ group.rect.topleft."""
        for layer in self.layers:
            surface = layer.get_current_frame()
            if surface is None:
                continue
            screen.blit(self.get_scaled_surface(surface), self._rect.topleft)

    def set_position(self, x, y):
        """РџРµСЂРµРјРµСЃС‚РёС‚СЊ group РЅР° СЌРєСЂР°РЅРµ Р±РµР· РёР·РјРµРЅРµРЅРёСЏ РµРіРѕ Р±Р°Р·РѕРІРѕРіРѕ СЂР°Р·РјРµСЂР°."""
        old_position = self._base_rect.topleft
        self._base_rect.topleft = (int(x), int(y))
        self._base_hit_rect.move_ip(
            self._base_rect.x - old_position[0],
            self._base_rect.y - old_position[1],
        )
        self.apply_scale()

    def set_rect(self, rect):
        """Р—Р°РґР°С‚СЊ Р±Р°Р·РѕРІС‹Р№ rect group-Р° Рё СЃРёРЅС…СЂРѕРЅРёР·РёСЂРѕРІР°С‚СЊ hit_rect."""
        self._base_rect = pygame.Rect(rect)
        self._base_hit_rect = self._base_rect.copy()
        self.apply_scale()

    def set_hit_rect(self, rect):
        """Р—Р°РґР°С‚СЊ Р±Р°Р·РѕРІСѓСЋ РѕР±Р»Р°СЃС‚СЊ РєР»РёРєР° group-Р°.

        hit_rect РјРѕР¶РµС‚ РѕС‚Р»РёС‡Р°С‚СЊСЃСЏ РѕС‚ rect, РЅРѕ РѕСЃС‚Р°РµС‚СЃСЏ РіРµРѕРјРµС‚СЂРёРµР№ РІСЃРµРіРѕ group-Р°,
        Р° РЅРµ РѕС‚РґРµР»СЊРЅРѕРіРѕ СЃР»РѕСЏ.
        """
        self._base_hit_rect = pygame.Rect(rect)
        self.apply_scale()

    def set_scale_factor(self, scale_factor):
        """Р—Р°РґР°С‚СЊ РјР°СЃС€С‚Р°Р± РІСЃРµРіРѕ group-Р° РѕС‚ РёСЃС…РѕРґРЅРѕРіРѕ Р±Р°Р·РѕРІРѕРіРѕ rect."""
        self.scale_factor = float(scale_factor)
        self.apply_scale()

    def add_layer(self, layer):
        """Р”РѕР±Р°РІРёС‚СЊ СЃР»РѕР№ РІ РєРѕРЅРµС† РїРѕСЂСЏРґРєР° РѕС‚СЂРёСЃРѕРІРєРё."""
        if isinstance(layer, Layer):
            self.layers.append(layer)
            return layer

        if isinstance(layer, dict):
            new_layer = Layer(
                name=layer["name"],
                frames=list(layer.get("frames", [])),
                current_frame_index=layer.get("current_frame_index", 0),
            )
            self.layers.append(new_layer)
            return new_layer

        raise TypeError(f"РќРµРїРѕРґРґРµСЂР¶РёРІР°РµРјС‹Р№ С‚РёРї СЃР»РѕСЏ: {type(layer)!r}")

    def set_layer_frame(self, layer_name, frame_index):
        """РЈСЃС‚Р°РЅРѕРІРёС‚СЊ С‚РµРєСѓС‰РёР№ РєР°РґСЂ СЃР»РѕСЏ."""
        self.get_layer(layer_name).set_frame(frame_index)

    def set_layer_frames(self, layer_name, frames):
        """Р—Р°РјРµРЅРёС‚СЊ СЃРїРёСЃРѕРє РєР°РґСЂРѕРІ СЃР»РѕСЏ."""
        layer = self.get_layer(layer_name)
        layer.frames = list(frames)
        layer.set_frame(0)
        if self._base_rect.size == (0, 0):
            self.refresh_rect_from_layers()
            self.apply_scale()

    def get_layer(self, layer_name):
        """РќР°Р№С‚Рё СЃР»РѕР№ РїРѕ РёРјРµРЅРё."""
        for layer in self.layers:
            if layer.name == layer_name:
                return layer
        raise ValueError(f"РќРµРёР·РІРµСЃС‚РЅС‹Р№ СЃР»РѕР№: {layer_name}")

    def refresh_rect_from_layers(self):
        """Р’С‹СЃС‚Р°РІРёС‚СЊ СЂР°Р·РјРµСЂ group-Р° РїРѕ РїРµСЂРІРѕРјСѓ РґРѕСЃС‚СѓРїРЅРѕРјСѓ РєР°РґСЂСѓ.

        Р­С‚Рѕ РІСЃРїРѕРјРѕРіР°С‚РµР»СЊРЅС‹Р№ СЂРµР¶РёРј РґР»СЏ СЂР°РЅРЅРёС… РїСЂРѕС‚РѕС‚РёРїРѕРІ. Р’ Р·СЂРµР»РѕРј РєРѕРґРµ СЌРєСЂР°РЅ РёР»Рё
        СЃР±РѕСЂРєР° group-Р° РѕР±С‹С‡РЅРѕ Р·Р°РґР°СЋС‚ rect СЏРІРЅРѕ.
        """
        for layer in self.layers:
            surface = layer.get_current_frame()
            if surface is not None:
                self._base_rect.size = surface.get_size()
                self._base_hit_rect = self._base_rect.copy()
                return

    def apply_scale(self):
        """РџРµСЂРµСЃС‡РёС‚Р°С‚СЊ rect Рё hit_rect РѕС‚ Р±Р°Р·РѕРІРѕР№ РіРµРѕРјРµС‚СЂРёРё Рё scale_factor."""
        self._rect = self.scale_rect(self._base_rect, self.scale_factor)
        self._hit_rect = self.scale_rect(self._base_hit_rect, self.scale_factor)

    def get_scaled_surface(self, surface):
        """Р’РµСЂРЅСѓС‚СЊ surface, РјР°СЃС€С‚Р°Р±РёСЂРѕРІР°РЅРЅС‹Р№ С‚РµРєСѓС‰РёРј scale_factor."""
        if self.scale_factor == 1.0:
            return surface
        width, height = surface.get_size()
        scaled_size = (
            max(1, round(width * self.scale_factor)),
            max(1, round(height * self.scale_factor)),
        )
        return pygame.transform.smoothscale(surface, scaled_size)

    @staticmethod
    def scale_rect(rect, scale_factor):
        """РњР°СЃС€С‚Р°Р±РёСЂРѕРІР°С‚СЊ РїСЂСЏРјРѕСѓРіРѕР»СЊРЅРёРє РѕС‚ РµРіРѕ Р±Р°Р·РѕРІРѕР№ Р»РµРІРѕР№ РІРµСЂС…РЅРµР№ С‚РѕС‡РєРё."""
        return pygame.Rect(
            rect.x,
            rect.y,
            max(0, round(rect.width * scale_factor)),
            max(0, round(rect.height * scale_factor)),
        )


