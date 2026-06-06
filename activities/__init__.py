"""Пакет визуальных Activity.

Activity - это визуально-поведенческий режим или процесс. Он может жить один
кадр, несколько секунд или весь игровой сеанс. Правила игры здесь не живут.
"""

from activities.base_activity import Activity
from activities.bot_hand_activity import BotHandActivity
from activities.player_hand_activity import VisibleCardsHandDecorator

__all__ = ["Activity", "BotHandActivity", "VisibleCardsHandDecorator"]
