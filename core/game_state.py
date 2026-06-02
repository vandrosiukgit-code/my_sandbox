"""Р§РµСЂРЅРѕРІС‹Рµ СЃС‚СЂСѓРєС‚СѓСЂС‹ РёРіСЂРѕРІРѕРіРѕ СЃРѕСЃС‚РѕСЏРЅРёСЏ РґР»СЏ С„РёРєСЃС‚СѓСЂ.

РќР° СЌС‚РѕРј СЌС‚Р°РїРµ Р·РґРµСЃСЊ РЅРµС‚ РїСЂР°РІРёР» РёРіСЂС‹. Р­С‚Рё dataclass-С‹ РЅСѓР¶РЅС‹, С‡С‚РѕР±С‹ РјРѕР¶РЅРѕ Р±С‹Р»Рѕ
РѕРїРёСЃР°С‚СЊ СЃРѕСЃС‚РѕСЏРЅРёРµ СЂСѓРєР°РјРё: РєР°РєРёРµ РєР°СЂС‚С‹ СЃСѓС‰РµСЃС‚РІСѓСЋС‚ Рё РІ РєР°РєРёС… Р»РѕРіРёС‡РµСЃРєРёС… Р·РѕРЅР°С…
РѕРЅРё Р»РµР¶Р°С‚. GameController Р±СѓРґРµС‚ РїСЂРёРЅРёРјР°С‚СЊ С‚Р°РєРѕР№ snapshot Рё РѕС‚РґР°РІР°С‚СЊ СЌРєСЂР°РЅСѓ
РІРёР·СѓР°Р»СЊРЅС‹Рµ Р·Р°РїСЂРѕСЃС‹.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CardState:
    """РњРёРЅРёРјР°Р»СЊРЅРѕРµ РѕРїРёСЃР°РЅРёРµ РѕРґРЅРѕР№ РєР°СЂС‚С‹ РІ Р»РѕРіРёС‡РµСЃРєРѕРј СЃРѕСЃС‚РѕСЏРЅРёРё.

    Attributes:
        card_id: РЎС‚Р°Р±РёР»СЊРЅС‹Р№ ID РєР°СЂС‚С‹. РўР°РєРѕР№ Р¶Рµ ID РґРѕР»Р¶РµРЅ РёРјРµС‚СЊ Group РєР°СЂС‚С‹.
        rank: Р Р°РЅРі РєР°СЂС‚С‹: 6, 7, 8, 9, 10, j, q, k, a Рё С‚.Рґ.
        suit: РњР°СЃС‚СЊ РєР°СЂС‚С‹: clubs, diamonds, hearts, spades.
        frame: Р›РѕРіРёС‡РµСЃРєР°СЏ Р·РѕРЅР°, РіРґРµ РєР°СЂС‚Р° РЅР°С…РѕРґРёС‚СЃСЏ СЃРµР№С‡Р°СЃ.
        face_up: РћС‚РєСЂС‹С‚Р° Р»Рё РєР°СЂС‚Р° Р»РёС†РѕРј РІРІРµСЂС….
    """

    card_id: str
    rank: str
    suit: str
    frame: str
    face_up: bool = True


@dataclass
class GameState:
    """РњРёРЅРёРјР°Р»СЊРЅС‹Р№ snapshot СЃРѕСЃС‚РѕСЏРЅРёСЏ РёРіСЂС‹.

    cards С…СЂР°РЅРёС‚ СЃР°РјРё РєР°СЂС‚С‹ РїРѕ card_id.
    frames С…СЂР°РЅРёС‚ РїРѕСЂСЏРґРѕРє card_id РІРЅСѓС‚СЂРё Р»РѕРіРёС‡РµСЃРєРёС… Р·РѕРЅ.
    """

    cards: dict[str, CardState] = field(default_factory=dict)
    frames: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_cards(cls, cards):
        """РЎРѕР±СЂР°С‚СЊ GameState РёР· СЃРїРёСЃРєР° CardState.

        РњРµС‚РѕРґ СѓРґРѕР±РµРЅ РґР»СЏ С„РёРєСЃС‚СѓСЂ: РјРѕР¶РЅРѕ РѕРїРёСЃР°С‚СЊ РєР°СЂС‚С‹ СЃРїРёСЃРєРѕРј, Р° frames Р±СѓРґСѓС‚
        РїРѕСЃС‚СЂРѕРµРЅС‹ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё РїРѕ РїРѕР»СЋ card.frame.
        """
        state = cls()
        for card in cards:
            state.cards[card.card_id] = card
            state.frames.setdefault(card.frame, []).append(card.card_id)
        return state

    def get_frame_card_ids(self, frame_id):
        """Р’РµСЂРЅСѓС‚СЊ card_id РІ СѓРєР°Р·Р°РЅРЅРѕР№ Р»РѕРіРёС‡РµСЃРєРѕР№ Р·РѕРЅРµ."""
        return tuple(self.frames.get(frame_id, ()))


