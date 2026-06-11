# Code Review Report: `player_turn_activity(3).py`

## 1. Краткое резюме

`PlayerTurnActivity` — небольшой orchestration-activity для визуального процесса хода игрока. Сейчас класс почти полностью делегирует работу `play_area_slots_activity`: запуск, обновление, debug draw, fixture и доступ к generated groups.

Файл выглядит как заготовка под будущий уровень управления ходом. Главный риск не в объеме кода, а в нечеткой модели жизненного цикла: `start()`, `start_turn()`, `turn_active`, `finish()` и `_finished` могут начать конфликтовать, когда появится реальная логика хода.

## 2. Назначение класса

Класс отвечает за:

- запуск визуальной активности зоны хода;
- делегирование `update()` вложенной активности;
- хранение `turn_context`;
- флаг `turn_active`;
- опциональное владение `play_area_slots_activity`;
- проброс debug draw и fixture;
- предоставление generated groups наружу.

На текущем этапе это скорее wrapper/decorator над `play_area_slots_activity`, чем полноценная turn activity.

## 3. Основные проблемы

### 3.1. `start()` автоматически активирует ход

```python
super().start()
self.turn_active = True
```

Это делает обычный запуск Activity эквивалентным началу хода. Из-за этого `start_turn()` теряет часть смысла: ход может стать активным без явного `turn_context`.

Проблемный сценарий:

1. Экран вызывает `activity.start()` автоматически.
2. `turn_active` становится `True`.
3. Позже контроллер вызывает `start_turn(context)`.
4. Метод возвращает `False`, потому что ход уже активен.
5. `turn_context` так и остается `None`.

Риск: контроллер не сможет нормально передать данные хода, если базовый lifecycle уже стартовал активность.

### 3.2. `start_turn()` вызывает `self.start()`, но перед этим уже ставит `turn_active = True`

```python
self.turn_context = dict(turn_context or {})
self.turn_active = True
self.start()
return True
```

А `start()` содержит:

```python
if self.started:
    return
```

На первый взгляд это работает, но логика становится неочевидной: `start_turn()` одновременно отвечает и за состояние хода, и за lifecycle Activity.

Лучше разделить:

- `start()` — только lifecycle активности;
- `start_turn()` — только начало конкретного хода;
- `finish_turn()` или `end_turn()` — завершение конкретного хода.

### 3.3. Нет метода завершения одного хода без завершения Activity

Сейчас есть только `finish()`:

```python
self.turn_active = False
self.turn_context = None
super().finish()
```

Но `finish()` завершает всю Activity. Для долгоживущего экрана это может быть слишком грубо.

Если один и тот же `PlayerTurnActivity` должен переживать много ходов, нужен отдельный метод:

```python
def finish_turn(self):
    self.turn_active = False
    self.turn_context = None
```

А `finish()` должен завершать сам режим целиком.

### 3.4. `turn_context` почти не используется

`turn_context` сохраняется, но не влияет ни на один метод:

```python
self.turn_context = dict(turn_context or {})
```

Это нормально для заготовки, но сейчас поле выглядит декларативным. В будущем важно определить, что именно туда попадает:

- id игрока;
- id выбранной карты;
- состояние стола;
- разрешенные действия;
- visual command;
- callback/token хода;
- данные для анимации.

Без явного контракта `turn_context` может быстро превратиться в неструктурированный словарь.

### 3.5. `update()` запускает Activity автоматически

```python
if not self.started:
    self.start()
    return
```

Это удобно, но опасно в связке с проблемой 3.1. Первый же `update()` автоматически сделает `turn_active = True`, даже если контроллер еще не начал ход.

Если `turn_active` должен означать именно активный ход, то `update()` не должен сам создавать это состояние.

### 3.6. Слишком мягкий контракт `play_area_slots_activity`

Валидация требует только:

```python
start()
update()
finish()
```

Но дальше класс опционально ожидает дополнительные методы:

- `draw_debug_overlay()` или `draw()`;
- `iter_generated_groups()`;
- `apply_fixture()`;
- `is_finished()`.

Это гибко, но размывает контракт. При расширении лучше ввести явный протокол/интерфейс или хотя бы документированный минимальный набор методов.

### 3.7. `draw()` рисует только debug overlay

```python
def draw(self, screen):
    self.draw_debug_overlay(screen)
```

Если generated groups рисуются внешним `GameScreen`, это нормально. Но название метода может ввести в заблуждение: он не рисует саму turn activity, а только debug/делегированный draw.

Лучше уточнить docstring или переименовать внутреннюю семантику.

### 3.8. `finish()` может не завершить вложенную активность, если `owns_play_area_slots_activity=False`

```python
if self.owns_play_area_slots_activity:
    ...
```

Это правильно для ownership-модели, но важно помнить: если `PlayerTurnActivity` не владеет вложенной активностью, то после `finish()` вложенная активность может продолжить жить.

Это не баг, но потенциальный источник утечек состояния, если ownership неправильно задан при создании.

### 3.9. `is_finished()` просто возвращает `_finished`

```python
def is_finished(self):
    return self._finished
```

Это, вероятно, повторяет поведение базового `Activity`. Если метод не добавляет новой семантики, его можно убрать. Если он оставлен для явности — это допустимо, но пользы немного.

## 4. Главный архитектурный риск

Самая важная проблема: `PlayerTurnActivity` смешивает два разных жизненных цикла.

### Lifecycle Activity

- `start()`
- `update()`
- `finish()`
- `is_finished()`

### Lifecycle хода

- `start_turn(context)`
- `turn_active`
- `turn_context`
- будущий `finish_turn()` / `cancel_turn()` / `commit_turn()`

Сейчас эти два жизненных цикла частично склеены. Пока класс маленький, это не мешает. Но когда появятся реальные turn-level effects, selection, controller commands и анимации, эта связка может стать источником трудноуловимых багов.

## 5. Рекомендуемая модель исправления

### Вариант 1. Activity живет долго, ход запускается отдельно

```python
def start(self):
    if self.started:
        return
    super().start()
    if not getattr(self.play_area_slots_activity, "started", False):
        self.play_area_slots_activity.start()
```

```python
def start_turn(self, turn_context):
    if self.turn_active:
        return False
    if not self.started:
        self.start()
    self.turn_context = dict(turn_context or {})
    self.turn_active = True
    return True
```

```python
def finish_turn(self):
    self.turn_active = False
    self.turn_context = None
```

Так `start()` больше не означает начало хода.

### Вариант 2. Activity создается на один ход

Если `PlayerTurnActivity` должен жить ровно один ход, тогда `start()` может активировать ход, но `turn_context` нужно передавать в `__init__`:

```python
def __init__(self, play_area_slots_activity, turn_context=None, owns_play_area_slots_activity=False):
    ...
    self.turn_context = dict(turn_context or {})
```

Тогда `start_turn()` может быть вообще не нужен.

## 6. Приоритет исправлений

### Высокий приоритет

1. Развести `start()` и `start_turn()`.
2. Добавить отдельный `finish_turn()` / `end_turn()`.
3. Решить, является ли `PlayerTurnActivity` долгоживущей активностью или активностью на один ход.

### Средний приоритет

4. Описать контракт `turn_context`.
5. Уточнить контракт `play_area_slots_activity`.
6. Уточнить смысл `draw()` и debug draw.

### Низкий приоритет

7. Убрать или оставить с комментарием дублирующий `is_finished()`.
8. Добавить docstring к `iter_generated_groups()` и `apply_fixture()`.

## 7. Возможная минимальная правка

```python
def start(self):
    if self.started:
        return
    super().start()
    if not getattr(self.play_area_slots_activity, "started", False):
        self.play_area_slots_activity.start()


def start_turn(self, turn_context):
    """Start one visual turn with controller-facing context."""
    if self.turn_active:
        return False
    if not self.started:
        self.start()
    self.turn_context = dict(turn_context or {})
    self.turn_active = True
    return True


def finish_turn(self):
    """Finish the current visual turn without destroying the activity."""
    self.turn_active = False
    self.turn_context = None
```

Эта правка сохраняет текущую архитектуру, но делает семантику безопаснее.

## 8. Итог

Файл выглядит аккуратно и пока не содержит сложной логики. Основная проблема — не синтаксис и не конкретный баг, а будущий конфликт жизненных циклов.

`PlayerTurnActivity` нужно как можно раньше определить как одну из двух сущностей:

1. долгоживущий координатор ходов;
2. одноразовая Activity на один конкретный ход.

Сейчас код находится между этими двумя моделями. Это главный источник потенциальных ошибок.
