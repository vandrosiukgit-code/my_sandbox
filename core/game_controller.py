"""Черновой GameController для работы с фикстурами состояния.

Это не реализация правил игры. Сейчас контроллер нужен как архитектурная
заглушка: он хранит snapshot состояния, принимает события от GameScreen и
отдает экрану текущее фикстурное состояние.
"""

from base import BaseGameController
from core.game_state import CardState, GameState


class GameController(BaseGameController):
    """Черновой контроллер игрового состояния без правил игры."""

    DEFAULT_ZONES = ("deck", "bottom_hand", "top_hand", "battle_table", "discard")

    def __init__(self, initial_state=None):
        """Создать контроллер.

        Args:
            initial_state: Необязательный GameState. Если передан, контроллер
                будет работать с ним как с фикстурой.
        """
        self.state = initial_state or GameState(zones={zone: [] for zone in self.DEFAULT_ZONES})
        self.clicked_actor_ids = []

    def start_game(self):
        """Инициализировать игру.

        Пока правил нет, метод ничего не рассчитывает. Экран будет читать
        текущее состояние через get_state() и сам интерпретировать фикстуру.
        """

    def load_fixture(self, state):
        """Загрузить готовый snapshot состояния.

        Этот метод нужен на этапе разработки, когда GameController еще не
        умеет сам раздавать карты и менять зоны по правилам.
        """
        self.state = state

    def on_actor_clicked(self, actor_id):
        """Принять клик по actor ID от GameScreen.

        Пока настоящей логики нет, контроллер только сохраняет историю кликов.
        Позже здесь появятся проверки правил: можно ли выбрать карту, можно ли
        сделать ход, нужно ли запустить визуальный процесс и т.д.
        """
        self.clicked_actor_ids.append(actor_id)

    def get_state(self):
        """Вернуть текущий snapshot состояния.

        На этапе фикстур именно GameScreen будет читать зоны из GameState и
        решать, какие GuiActor активировать и куда поставить на экране.
        """
        return self.state

    @staticmethod
    def create_fixture_state():
        """Создать маленькую фикстуру для ручной проверки экрана.

        Фикстура имитирует ситуацию: у нижнего игрока на руке шесть карт.
        Это не результат правил раздачи, а просто удобный snapshot для
        разработки GameScreen и GuiActorStore.
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
