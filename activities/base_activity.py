"""Базовая реализация Activity.

Activity - это временный визуальный процесс, которым владеет GameScreen.
Она получает нужные GuiActor снаружи и меняет только их визуальное состояние:
позицию, видимость, прозрачность, текущий кадр и т.д.

Важно: Activity не должна менять GameController и не должна знать правила
игры. Если после визуального процесса нужно продолжить сценарий, это решает
экран или контроллер на более высоком уровне.
"""

from base import BaseActivity


class Activity(BaseActivity):
    """Базовый класс для визуальных процессов."""

    def __init__(self, actor_ids=None, duration=0.0):
        """Создать Activity.

        Args:
            actor_ids: ID actor-ов, к которым относится активность.
            duration: Желаемая длительность в секундах. Значение 0 означает,
                что базовая Activity завершится сразу после первого update().
        """
        self.actor_ids = tuple(actor_ids or ())
        self.duration = max(0.0, float(duration))
        self.elapsed = 0.0
        self.started = False
        self._finished = False

    def start(self):
        """Запустить визуальный процесс.

        GameScreen вызывает start() при добавлении Activity. Наследники могут
        переопределять метод, но обычно должны вызывать super().start().
        """
        self.started = True
        self._finished = False
        self.elapsed = 0.0

    def update(self, dt):
        """Обновить Activity на шаг dt.

        Базовая реализация только считает время и завершает процесс, когда
        elapsed >= duration. Конкретные активности будут переопределять
        apply(), чтобы менять GuiActor во времени.
        """
        if self._finished:
            return

        if not self.started:
            self.start()

        self.elapsed += dt
        self.apply(self.get_progress())

        if self.elapsed >= self.duration:
            self.finish()

    def apply(self, progress):
        """Применить визуальное состояние по progress.

        Args:
            progress: Число от 0.0 до 1.0. Наследники используют его для
                интерполяции позиции, alpha, кадра и других свойств.

        Базовая Activity ничего не меняет. Это осознанная заглушка.
        """
        _ = progress

    def is_finished(self):
        """Вернуть True, если Activity завершена."""
        return self._finished

    def finish(self):
        """Принудительно завершить Activity."""
        self._finished = True
        self.started = False

    def get_progress(self):
        """Вернуть прогресс выполнения от 0.0 до 1.0."""
        if self.duration <= 0:
            return 1.0
        return max(0.0, min(1.0, self.elapsed / self.duration))
