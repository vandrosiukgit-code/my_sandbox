"""Р§РµСЂРЅРѕРІРѕР№ GameController РґР»СЏ СЂР°Р±РѕС‚С‹ СЃ С„РёРєСЃС‚СѓСЂР°РјРё СЃРѕСЃС‚РѕСЏРЅРёСЏ.

Р­С‚Рѕ РЅРµ СЂРµР°Р»РёР·Р°С†РёСЏ РїСЂР°РІРёР» РёРіСЂС‹. РЎРµР№С‡Р°СЃ РєРѕРЅС‚СЂРѕР»Р»РµСЂ РЅСѓР¶РµРЅ РєР°Рє Р°СЂС…РёС‚РµРєС‚СѓСЂРЅР°СЏ
Р·Р°РіР»СѓС€РєР°: РѕРЅ С…СЂР°РЅРёС‚ snapshot СЃРѕСЃС‚РѕСЏРЅРёСЏ, РїСЂРёРЅРёРјР°РµС‚ СЃРѕР±С‹С‚РёСЏ РѕС‚ GameScreen Рё
РѕС‚РґР°РµС‚ СЌРєСЂР°РЅСѓ С‚РµРєСѓС‰РµРµ С„РёРєСЃС‚СѓСЂРЅРѕРµ СЃРѕСЃС‚РѕСЏРЅРёРµ.
"""

from base import BaseGameController
from core.game_state import CardState, GameState


class GameController(BaseGameController):
    """Р§РµСЂРЅРѕРІРѕР№ РєРѕРЅС‚СЂРѕР»Р»РµСЂ РёРіСЂРѕРІРѕРіРѕ СЃРѕСЃС‚РѕСЏРЅРёСЏ Р±РµР· РїСЂР°РІРёР» РёРіСЂС‹."""

    DEFAULT_FRAMES = ("deck", "bottom_hand", "top_hand", "battle_table", "discard")

    def __init__(self, initial_state=None):
        """РЎРѕР·РґР°С‚СЊ РєРѕРЅС‚СЂРѕР»Р»РµСЂ.

        Args:
            initial_state: РќРµРѕР±СЏР·Р°С‚РµР»СЊРЅС‹Р№ GameState. Р•СЃР»Рё РїРµСЂРµРґР°РЅ, РєРѕРЅС‚СЂРѕР»Р»РµСЂ
                Р±СѓРґРµС‚ СЂР°Р±РѕС‚Р°С‚СЊ СЃ РЅРёРј РєР°Рє СЃ С„РёРєСЃС‚СѓСЂРѕР№.
        """
        self.state = initial_state or GameState(frames={frame: [] for frame in self.DEFAULT_FRAMES})
        self.clicked_group_ids = []

    def start_game(self):
        """РРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°С‚СЊ РёРіСЂСѓ.

        РџРѕРєР° РїСЂР°РІРёР» РЅРµС‚, РјРµС‚РѕРґ РЅРёС‡РµРіРѕ РЅРµ СЂР°СЃСЃС‡РёС‚С‹РІР°РµС‚. Р­РєСЂР°РЅ Р±СѓРґРµС‚ С‡РёС‚Р°С‚СЊ
        С‚РµРєСѓС‰РµРµ СЃРѕСЃС‚РѕСЏРЅРёРµ С‡РµСЂРµР· get_state() Рё СЃР°Рј РёРЅС‚РµСЂРїСЂРµС‚РёСЂРѕРІР°С‚СЊ С„РёРєСЃС‚СѓСЂСѓ.
        """

    def load_fixture(self, state):
        """Р—Р°РіСЂСѓР·РёС‚СЊ РіРѕС‚РѕРІС‹Р№ snapshot СЃРѕСЃС‚РѕСЏРЅРёСЏ.

        Р­С‚РѕС‚ РјРµС‚РѕРґ РЅСѓР¶РµРЅ РЅР° СЌС‚Р°РїРµ СЂР°Р·СЂР°Р±РѕС‚РєРё, РєРѕРіРґР° GameController РµС‰Рµ РЅРµ
        СѓРјРµРµС‚ СЃР°Рј СЂР°Р·РґР°РІР°С‚СЊ РєР°СЂС‚С‹ Рё РјРµРЅСЏС‚СЊ Р·РѕРЅС‹ РїРѕ РїСЂР°РІРёР»Р°Рј.
        """
        self.state = state

    def on_group_clicked(self, group_id):
        """РџСЂРёРЅСЏС‚СЊ РєР»РёРє РїРѕ group ID РѕС‚ GameScreen.

        РџРѕРєР° РЅР°СЃС‚РѕСЏС‰РµР№ Р»РѕРіРёРєРё РЅРµС‚, РєРѕРЅС‚СЂРѕР»Р»РµСЂ С‚РѕР»СЊРєРѕ СЃРѕС…СЂР°РЅСЏРµС‚ РёСЃС‚РѕСЂРёСЋ РєР»РёРєРѕРІ.
        РџРѕР·Р¶Рµ Р·РґРµСЃСЊ РїРѕСЏРІСЏС‚СЃСЏ РїСЂРѕРІРµСЂРєРё РїСЂР°РІРёР»: РјРѕР¶РЅРѕ Р»Рё РІС‹Р±СЂР°С‚СЊ РєР°СЂС‚Сѓ, РјРѕР¶РЅРѕ Р»Рё
        СЃРґРµР»Р°С‚СЊ С…РѕРґ, РЅСѓР¶РЅРѕ Р»Рё Р·Р°РїСѓСЃС‚РёС‚СЊ РІРёР·СѓР°Р»СЊРЅС‹Р№ РїСЂРѕС†РµСЃСЃ Рё С‚.Рґ.
        """
        self.clicked_group_ids.append(group_id)

    def handle_input(self, input_event):
        """Receive normalized input from GameScreen and return visual commands.

        This draft controller records input but does not implement rules yet.
        Later this method will validate intents against GameState, mutate state,
        and return VisualCommand objects such as play_card or deal_cards.
        """
        if not hasattr(self, "input_events"):
            self.input_events = []
        self.input_events.append(input_event)

        if input_event.group_id and input_event.type in ("click", "double_click"):
            self.on_group_clicked(input_event.group_id)

        return ()

    def get_state(self):
        """Р’РµСЂРЅСѓС‚СЊ С‚РµРєСѓС‰РёР№ snapshot СЃРѕСЃС‚РѕСЏРЅРёСЏ.

        РќР° СЌС‚Р°РїРµ С„РёРєСЃС‚СѓСЂ РёРјРµРЅРЅРѕ GameScreen Р±СѓРґРµС‚ С‡РёС‚Р°С‚СЊ Р·РѕРЅС‹ РёР· GameState Рё
        СЂРµС€Р°С‚СЊ, РєР°РєРёРµ Group Р°РєС‚РёРІРёСЂРѕРІР°С‚СЊ Рё РєСѓРґР° РїРѕСЃС‚Р°РІРёС‚СЊ РЅР° СЌРєСЂР°РЅРµ.
        """
        return self.state

    @staticmethod
    def create_fixture_state():
        """РЎРѕР·РґР°С‚СЊ РјР°Р»РµРЅСЊРєСѓСЋ С„РёРєСЃС‚СѓСЂСѓ РґР»СЏ СЂСѓС‡РЅРѕР№ РїСЂРѕРІРµСЂРєРё СЌРєСЂР°РЅР°.

        Р¤РёРєСЃС‚СѓСЂР° РёРјРёС‚РёСЂСѓРµС‚ СЃРёС‚СѓР°С†РёСЋ: Сѓ РЅРёР¶РЅРµРіРѕ РёРіСЂРѕРєР° РЅР° СЂСѓРєРµ С€РµСЃС‚СЊ РєР°СЂС‚.
        Р­С‚Рѕ РЅРµ СЂРµР·СѓР»СЊС‚Р°С‚ РїСЂР°РІРёР» СЂР°Р·РґР°С‡Рё, Р° РїСЂРѕСЃС‚Рѕ СѓРґРѕР±РЅС‹Р№ snapshot РґР»СЏ
        СЂР°Р·СЂР°Р±РѕС‚РєРё GameScreen Рё GroupStore.
        """
        return GameState.from_cards(
            [
                CardState("card_6_clubs", "6", "clubs", "bottom_hand"),
                CardState("card_7_clubs", "7", "clubs", "bottom_hand"),
                CardState("card_8_clubs", "8", "clubs", "bottom_hand"),
                CardState("card_9_clubs", "9", "clubs", "bottom_hand"),
                CardState("card_10_clubs", "10", "clubs", "bottom_hand"),
                CardState("card_j_clubs", "j", "clubs", "bottom_hand"),
            ]
        )


