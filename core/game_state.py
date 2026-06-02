"""Черновые структуры игрового состояния для фикстур.

На этом этапе здесь нет правил игры. Эти dataclass-ы нужны, чтобы можно было
описать состояние руками: какие карты существуют и в каких логических зонах
они лежат. GameController будет принимать такой snapshot и отдавать экрану
визуальные запросы.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CardState:
    """Минимальное описание одной карты в логическом состоянии.

    Attributes:
        card_id: Стабильный ID карты. Такой же ID должен иметь Group карты.
        rank: Ранг карты: 6, 7, 8, 9, 10, j, q, k, a и т.д.
        suit: Масть карты: clubs, diamonds, hearts, spades.
        frame: Логическая зона, где карта находится сейчас.
        face_up: Открыта ли карта лицом вверх.
    """

    card_id: str
    rank: str
    suit: str
    frame: str
    face_up: bool = True


@dataclass
class GameState:
    """Минимальный snapshot состояния игры.

    cards хранит сами карты по card_id.
    frames хранит порядок card_id внутри логических зон.
    """

    cards: dict[str, CardState] = field(default_factory=dict)
    frames: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_cards(cls, cards):
        """Собрать GameState из списка CardState.

        Метод удобен для фикстур: можно описать карты списком, а frames будут
        построены автоматически по полю card.frame.
        """
        state = cls()
        for card in cards:
            state.cards[card.card_id] = card
            state.frames.setdefault(card.frame, []).append(card.card_id)
        return state

    def get_frame_card_ids(self, frame_id):
        """Вернуть card_id в указанной логической зоне."""
        return tuple(self.frames.get(frame_id, ()))


