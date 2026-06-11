# Отчёт о проблемах в `player_turn_activity.py`

**Предложенное имя файла:** `player_turn_activity_audit_report.md`

## Контекст

Файл содержит `PlayerTurnActivity` — высокоуровневую Activity для визуального процесса хода игрока в игровой области.

Сейчас класс является тонкой обёрткой над `play_area_slots_activity`:

```text
PlayerTurnActivity
-> start() делегирует start во вложенную PlayAreaSlotsActivity
-> update() делегирует update
-> draw() делегирует draw, если он есть
-> apply_fixture() делегирует fixture
-> finish() завершает вложенную activity
```

Такой класс может быть полезен как будущая точка расширения: сюда можно добавить turn-level effects, команды контроллера, focus, анимации и переходы состояния. Но в текущем виде он почти полностью проксирует другую activity и имеет несколько рисков жизненного цикла.

---

## 1. `PlayerTurnActivity` почти полностью дублирует lifecycle вложенной activity

### Проблема

Методы класса в основном просто вызывают такие же методы у `play_area_slots_activity`:

```python
def start(self):
    super().start()
    self.play_area_slots_activity.start()

def update(self, dt):
    if not self.started:
        self.start()
    self.play_area_slots_activity.update(dt)

def finish(self):
    self.play_area_slots_activity.finish()
    super().finish()
```

### Почему это может быть нормально

Если `PlayerTurnActivity` — заготовка под будущую turn-level orchestration, это допустимый временный каркас.

### Почему это может быть проблемой

Сейчас класс добавляет ещё один уровень lifecycle, но почти не добавляет своей логики. Это может привести к путанице:

- кто реально владеет `play_area_slots_activity`;
- кто должен её запускать;
- кто должен её завершать;
- можно ли использовать `play_area_slots_activity` отдельно;
- должна ли она жить дольше одного player turn.

### Рекомендация

Явно зафиксировать роль класса в комментарии или параметре владения:

```python
def __init__(self, play_area_slots_activity, owns_play_area_slots_activity=True):
    ...
    self.owns_play_area_slots_activity = owns_play_area_slots_activity
```

И завершать вложенную activity только если этот класс действительно ей владеет.

---

## 2. `start()` может повторно запускать `play_area_slots_activity`

### Проблема

Метод `start()` безусловно вызывает:

```python
self.play_area_slots_activity.start()
```

Если вложенная activity уже была запущена раньше, произойдёт повторный вызов.

### Почему это опасно

Если `PlayAreaSlotsActivity.start()` или её будущая версия будет неидемпотентной, повторный запуск может:

- пересоздать слоты;
- сбросить layout;
- сбросить анимации;
- повторно зарегистрировать вложенные activity;
- вызвать визуальный скачок.

### Рекомендация

Проверять состояние перед запуском:

```python
def start(self):
    super().start()
    if not getattr(self.play_area_slots_activity, "started", False):
        self.play_area_slots_activity.start()
```

---

## 3. `finish()` безусловно завершает `play_area_slots_activity`

### Проблема

Сейчас:

```python
def finish(self):
    self.play_area_slots_activity.finish()
    super().finish()
```

### Почему это опасно

Если `play_area_slots_activity` является долгоживущей activity игровой зоны, завершение одного хода игрока не обязательно должно завершать всю систему слотов.

Например, слоты на столе могут должны оставаться видимыми между ходами.

### Рекомендация

Разделить понятия:

```text
end player turn
```

и

```text
destroy play area slots activity
```

Возможный вариант:

```python
def finish(self):
    if self.owns_play_area_slots_activity:
        self.play_area_slots_activity.finish()
    super().finish()
```

Если слоты должны жить дольше хода, `finish()` должен завершать только состояние самого turn activity.

---

## 4. Нет проверки, что `play_area_slots_activity` передана и совместима

### Проблема

Конструктор принимает объект и сохраняет его без проверки:

```python
def __init__(self, play_area_slots_activity):
    super().__init__(duration=0.0)
    self.play_area_slots_activity = play_area_slots_activity
```

Дальше код безусловно вызывает:

```python
self.play_area_slots_activity.start()
self.play_area_slots_activity.update(dt)
self.play_area_slots_activity.apply_fixture(fixture)
self.play_area_slots_activity.finish()
```

### Почему это опасно

Если в конструктор случайно передать `None` или объект без нужных методов, ошибка произойдёт позже и будет менее понятной.

### Рекомендация

Добавить раннюю валидацию:

```python
if play_area_slots_activity is None:
    raise ValueError("PlayerTurnActivity requires play_area_slots_activity")
```

Можно также проверить минимальный интерфейс:

```python
for method_name in ("start", "update", "finish"):
    if not hasattr(play_area_slots_activity, method_name):
        raise TypeError(f"play_area_slots_activity must have {method_name}()")
```

---

## 5. `apply_fixture()` не проверяет наличие метода у вложенной activity

### Проблема

`draw()` написан осторожно:

```python
if hasattr(self.play_area_slots_activity, "draw"):
    self.play_area_slots_activity.draw(screen)
```

Но `apply_fixture()` вызывает метод без проверки:

```python
self.play_area_slots_activity.apply_fixture(fixture)
```

### Почему это опасно

Если вложенная activity не поддерживает fixture, код упадёт.

### Рекомендация

Либо сделать `apply_fixture()` обязательной частью интерфейса вложенной activity, либо проверять наличие метода:

```python
def apply_fixture(self, fixture):
    if hasattr(self.play_area_slots_activity, "apply_fixture"):
        self.play_area_slots_activity.apply_fixture(fixture)
```

Главное — выбрать единый контракт. Сейчас `draw()` считается опциональным, а `apply_fixture()` — обязательным.

---

## 6. `update()` может вызвать `start()`, а затем сразу `play_area_slots_activity.update(dt)`

### Поведение

```python
def update(self, dt):
    if not self.started:
        self.start()
    self.play_area_slots_activity.update(dt)
```

Если activity не была запущена, в одном кадре произойдёт:

```text
PlayerTurnActivity.start()
-> play_area_slots_activity.start()
-> play_area_slots_activity.update(dt)
```

### Почему это может быть нормально

Такой lazy-start часто используется в activity-системах.

### Потенциальная проблема

Если `play_area_slots_activity.start()` уже сама делает layout, sync или запуск вложенных activity, немедленный `update(dt)` может привести к двойной работе в первый кадр.

### Рекомендация

Оставить, если такой lifecycle принят во всём проекте.

Если нет — можно сделать ранний return:

```python
def update(self, dt):
    if not self.started:
        self.start()
        return
    self.play_area_slots_activity.update(dt)
```

Но это изменит поведение первого кадра, поэтому решение зависит от общего контракта `Activity`.

---

## 7. Не хранится информация о выбранной карте

### Проблема

Класс называется `PlayerTurnActivity`, но не принимает и не хранит выбранную карту, группу, индекс или команду хода.

Связанный код выбора карты может вызвать:

```python
player_turn_activity.start()
```

Но в `PlayerTurnActivity` нет параметра:

```python
selected_card
selected_group
selected_index
command
```

### Почему это опасно

Activity хода не знает, чем именно вызван ход. Она может только стартовать layout игровой области.

Это создаёт неявную зависимость: выбранная карта должна быть где-то ещё, например в `CardSelectionActivity`, `GameController` или глобальном состоянии.

### Рекомендация

Сделать входные данные хода явными.

Например:

```python
def start_turn(self, selected_card_id):
    self.selected_card_id = selected_card_id
    self.start()
```

Или:

```python
def start_with_selection(self, selection):
    self.selection = selection
    self.start()
```

Лучше передавать не visual `Group`, а игровую сущность:

```text
card_id
hand_index
controller command
```

---

## 8. Нет поля `selected_card` / `turn_context` в `__init__`

### Проблема

Даже если позже выбранная карта будет добавляться динамически, сейчас в `__init__` нет подготовленного места для состояния хода.

### Почему это опасно

Если другие части кода начнут читать `player_turn_activity.selected_card` до выбора, они получат `AttributeError`.

### Рекомендация

Заранее добавить turn context:

```python
self.turn_context = None
```

или:

```python
self.selected_card_id = None
self.selected_hand_index = None
```

---

## 9. Нет защиты от повторного старта хода

### Проблема

`start()` не проверяет, идёт ли уже ход.

Если пользователь дважды кликнет по карте или input-система отправит несколько событий, возможно повторное начало turn activity.

### Почему это опасно

В будущем это может привести к:

- повторной отправке команды в controller;
- повторной анимации;
- конфликту состояний;
- нескольким активным переходам.

### Рекомендация

Добавить явное состояние:

```python
self.turn_active = False
```

или использовать `started`.

Например:

```python
def start_turn(self, selection):
    if self.turn_active:
        return False
    self.turn_active = True
    self.turn_context = selection
    self.start()
    return True
```

---

## 10. `is_finished()` просто возвращает `_finished`, не учитывая вложенную activity

### Проблема

```python
def is_finished(self):
    return self._finished
```

Если `play_area_slots_activity` завершилась сама, `PlayerTurnActivity` об этом не узнаёт.

### Почему это может быть нормально

Если `PlayerTurnActivity` владеет состоянием завершения, а вложенная activity — просто долгоживущий сервис, всё нормально.

### Почему это может быть проблемой

Если завершение вложенной activity должно означать завершение player turn, `is_finished()` должен учитывать её состояние.

### Рекомендация

Определить контракт.

Возможный вариант:

```python
def is_finished(self):
    return self._finished or self.play_area_slots_activity.is_finished()
```

Но это подходит только если жизненные циклы действительно связаны.

---

## 11. `finish()` может повторно завершать уже завершённую вложенную activity

### Проблема

Метод не проверяет состояние:

```python
self.play_area_slots_activity.finish()
```

### Почему это опасно

Если `finish()` вложенной activity неидемпотентный, повторный вызов может:

- повторно удалять frames;
- повторно удалять activities из registry;
- вызывать ошибки при pop/remove;
- ломать состояние screen.

### Рекомендация

Проверять состояние:

```python
if not self.play_area_slots_activity.is_finished():
    self.play_area_slots_activity.finish()
```

или хотя бы:

```python
if hasattr(self.play_area_slots_activity, "is_finished"):
    if not self.play_area_slots_activity.is_finished():
        self.play_area_slots_activity.finish()
```

---

## 12. `draw()` проксирует отрисовку только если есть метод `draw`

### Поведение

```python
def draw(self, screen):
    if hasattr(self.play_area_slots_activity, "draw"):
        self.play_area_slots_activity.draw(screen)
```

### Почему это нормально

Это делает класс совместимым с activity без draw.

### Потенциальный вопрос

Если `play_area_slots_activity` всегда должна уметь рисовать, проверка может скрыть ошибку конфигурации. Activity будет работать, но ничего не отрисует, и это будет сложнее отладить.

### Рекомендация

Если draw обязателен — убрать `hasattr` и падать явно.

Если draw опционален — оставить и добавить комментарий.

---

## 13. Нет собственных turn-level effects, хотя docstring их обещает

### Проблема

Docstring говорит:

```text
Later it can coordinate turn-level effects,
controller commands, focus, and short actions
```

Но сейчас ничего из этого нет.

### Почему это не баг

Это явно stage-заготовка.

### Почему стоит отметить

Название `PlayerTurnActivity` уже создаёт ожидание, что класс управляет ходом игрока. Сейчас он управляет только делегированием slot placement.

### Рекомендация

Либо оставить как scaffold и добавить комментарий `TODO`, либо временно назвать класс более точно:

```python
PlayerTurnPlayAreaSlotsActivity
```

или

```python
PlayerTurnSlotPlacementActivity
```

Но если класс скоро будет расширяться, текущее имя можно оставить.

---

## 14. Нет type hints

### Проблема

Методы не имеют аннотаций:

```python
def __init__(self, play_area_slots_activity):
def update(self, dt):
def draw(self, screen):
def apply_fixture(self, fixture):
```

### Почему это опасно

Класс кажется простым, но он зависит от внешнего интерфейса `play_area_slots_activity`.

Без type hints непонятно, какие методы обязаны быть у вложенной activity.

### Рекомендация

Добавить минимальные type hints или Protocol:

```python
class PlayAreaSlotsLike(Protocol):
    started: bool
    def start(self) -> None: ...
    def update(self, dt: float) -> None: ...
    def finish(self) -> None: ...
    def apply_fixture(self, fixture: dict) -> None: ...
```

---

# Приоритет исправлений

## Высокий приоритет

1. Определить, владеет ли `PlayerTurnActivity` объектом `play_area_slots_activity`.
2. Не завершать `play_area_slots_activity` безусловно, если она должна жить дольше одного хода.
3. Добавить явный `turn_context` / `selected_card_id` / `selected_hand_index`.
4. Защититься от повторного запуска одного и того же хода.

## Средний приоритет

5. Проверять состояние вложенной activity перед `start()` и `finish()`.
6. Добавить валидацию `play_area_slots_activity` в `__init__`.
7. Сделать контракт `apply_fixture()` явным: обязательный метод или optional method.
8. Решить, должен ли `is_finished()` учитывать вложенную activity.

## Низкий приоритет

9. Добавить type hints или Protocol.
10. Добавить комментарий к lazy-start в `update()`.
11. Уточнить имя класса или добавить TODO, если класс пока является scaffold.
12. Решить, должен ли `draw()` падать явно при отсутствии draw у вложенной activity.

---

# Главный вывод

`PlayerTurnActivity` сейчас является не полноценной activity хода игрока, а тонким lifecycle-прокси над `PlayAreaSlotsActivity`.

Это нормально как временный каркас, но перед подключением реальной игровой логики нужно добавить явный контекст хода:

```text
какой игрок ходит
какая карта выбрана
из какой руки выбрана карта
какая команда должна уйти в GameController
какие визуальные эффекты должны сопровождать ход
когда ход считается завершённым
```

Самый важный архитектурный вопрос:

```text
PlayAreaSlotsActivity принадлежит PlayerTurnActivity
или
PlayAreaSlotsActivity является долгоживущей частью play area?
```

Если это долгоживущая часть play area, то текущий метод:

```python
def finish(self):
    self.play_area_slots_activity.finish()
    super().finish()
```

может быть опасным, потому что завершение одного хода удалит/остановит всю систему слотов.
