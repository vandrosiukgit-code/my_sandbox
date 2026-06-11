# Отчёт о проблемах в `visible_cards_hand_activity.py`

**Предложенное имя файла:** `visible_cards_hand_activity_audit_report.md`

## Контекст

Файл содержит `VisibleCardsHandDecorator` — декоратор над hand fan activity, который подменяет закрытые карты на видимые ресурсы карт.

По смыслу класс делает следующее:

```text
hand_activity владеет геометрией веера и generated groups
VisibleCardsHandDecorator владеет списком видимых карт
VisibleCardsHandDecorator назначает hand_activity.card_resource_provider
hand_activity создаёт группы, запрашивая resource key по индексу
```

Это удобный слой между игровой рукой и визуальной hand activity. Но текущая реализация довольно глубоко мутирует wrapped activity и зависит от её внутренних полей/методов.

---

## 1. Декоратор напрямую мутирует поля `hand_activity`

### Проблема

В `__init__` декоратор напрямую меняет состояние wrapped activity:

```python
self.hand_activity.card_resource_provider = self.get_card_resource_key
self.hand_activity.card_layer_name = "card"
self.hand_activity.card_count = len(self.card_resource_keys)
```

### Почему это опасно

`VisibleCardsHandDecorator` не просто “декорирует”, а перепрошивает внутреннее поведение `hand_activity`.

Если `hand_activity` уже использовалась где-то ещё, после оборачивания она изменит:

- источник ресурсов карт;
- имя слоя карты;
- количество карт;
- possibly future behavior.

### Рекомендация

Это допустимо для простого прототипа, но стоит явно зафиксировать контракт:

```text
VisibleCardsHandDecorator получает эксклюзивное владение hand_activity.
После оборачивания hand_activity нельзя использовать как независимую Activity.
```

Или добавить публичный метод у `hand_activity`:

```python
hand_activity.configure_card_resources(
    provider=self.get_card_resource_key,
    layer_name="card",
    card_count=len(self.card_resource_keys),
)
```

Так зависимость будет явной.

---

## 2. Нет проверки совместимости `hand_activity`

### Проблема

Класс ожидает, что `hand_activity` имеет поля и методы:

```python
card_resource_provider
card_layer_name
card_count
start()
update()
draw()
apply_fixture()
clear_generated_groups()
is_finished()
finish()
```

Но в `__init__` совместимость не проверяется.

### Почему это опасно

Если передать неподходящий объект, ошибка произойдёт позже и не в очевидном месте.

### Рекомендация

Добавить раннюю валидацию:

```python
required_methods = (
    "start",
    "update",
    "draw",
    "apply_fixture",
    "clear_generated_groups",
    "is_finished",
    "finish",
)

for method_name in required_methods:
    if not hasattr(hand_activity, method_name):
        raise TypeError(f"hand_activity must have {method_name}()")
```

Для полей лучше перейти на публичный configure-метод, чтобы не проверять mutable attributes напрямую.

---

## 3. `start()` может повторно запускать `hand_activity`

### Проблема

Метод:

```python
def start(self):
    super().start()
    self.hand_activity.start()
```

безусловно вызывает `start()` вложенной activity.

### Почему это опасно

Если `hand_activity.start()` не идемпотентный, повторный запуск может:

- пересоздать группы;
- сбросить layout;
- сбросить анимации;
- повторно добавить группы во frame;
- вызвать визуальный скачок.

### Рекомендация

Проверять состояние:

```python
def start(self):
    super().start()
    if not getattr(self.hand_activity, "started", False):
        self.hand_activity.start()
```

---

## 4. `update()` не делает lazy-start самого декоратора

### Проблема

В отличие от некоторых других Activity, здесь `update()` выглядит так:

```python
def update(self, dt):
    self.hand_activity.update(dt)
```

Если `VisibleCardsHandDecorator.update()` вызван до `VisibleCardsHandDecorator.start()`, поле `self.started` останется `False`.

При этом `hand_activity.update(dt)` может сама себя запустить, если у неё есть lazy-start.

### Почему это опасно

Может возникнуть состояние:

```text
decorator.started == False
hand_activity.started == True
```

Это рассинхронизация lifecycle.

### Рекомендация

Добавить тот же pattern:

```python
def update(self, dt):
    if not self.started:
        self.start()
    self.hand_activity.update(dt)
```

Или явно договориться, что декораторы не имеют собственного lifecycle и полностью следуют wrapped activity.

---

## 5. `finish()` безусловно завершает `hand_activity`

### Проблема

Метод:

```python
def finish(self):
    self.hand_activity.finish()
    super().finish()
```

### Почему это опасно

Если `hand_activity` используется ещё где-то, завершение декоратора завершит и её.

### Рекомендация

Добавить явную семантику владения:

```python
def __init__(..., owns_hand_activity=True):
    self.owns_hand_activity = owns_hand_activity

def finish(self):
    if self.owns_hand_activity:
        self.hand_activity.finish()
    super().finish()
```

Если декоратор всегда эксклюзивно владеет `hand_activity`, это нужно указать в docstring.

---

## 6. `is_finished()` полностью делегирован wrapped activity

### Проблема

```python
def is_finished(self):
    return self.hand_activity.is_finished()
```

Собственное поле `_finished` декоратора игнорируется.

### Почему это опасно

После вызова:

```python
super().finish()
```

у декоратора `_finished` станет `True`, но `is_finished()` всё равно вернёт состояние `hand_activity`.

Если `hand_activity.finish()` по какой-то причине не сработала или не выставила `_finished`, декоратор будет считаться незавершённым.

### Рекомендация

Учитывать оба состояния:

```python
def is_finished(self):
    return self._finished or self.hand_activity.is_finished()
```

Или полностью отказаться от собственного lifecycle декоратора, но тогда не вызывать `super().finish()`/`super().start()` как самостоятельное состояние.

---

## 7. `set_cards()` очищает generated-группы, но не пересоздаёт их сразу

### Проблема

Метод:

```python
self.hand_activity.clear_generated_groups()
self.card_resource_keys = next_keys
self.hand_activity.card_count = len(self.card_resource_keys)
```

После этого новые группы не создаются сразу.

Они появятся только если позже кто-то вызовет:

```python
hand_activity.sync_visual_groups()
hand_activity.apply_fan_layout()
hand_activity.apply_fixture(...)
hand_activity.start()
```

### Почему это опасно

Если `set_cards()` вызван напрямую во время runtime, рука может временно стать пустой и не восстановиться до следующего layout/update шага, если wrapped activity не пересинхронизируется сама.

### Рекомендация

После смены карт явно синхронизировать визуальное состояние:

```python
self.hand_activity.clear_generated_groups()
self.card_resource_keys = next_keys
self.hand_activity.card_count = len(self.card_resource_keys)

if getattr(self.hand_activity, "started", False):
    self.hand_activity.sync_visual_groups()
    self.hand_activity.apply_fan_layout()
```

Если эти методы не часть публичного API, нужно добавить один публичный метод:

```python
hand_activity.rebuild_visual_groups()
```

---

## 8. `set_cards()` зависит от `clear_generated_groups()`

### Проблема

Декоратор вызывает:

```python
self.hand_activity.clear_generated_groups()
```

Это довольно специфичный метод конкретной реализации hand activity.

### Почему это опасно

Если wrapped activity изменит способ управления группами, декоратор сломается.

### Рекомендация

Лучше иметь публичный метод на hand activity:

```python
hand_activity.set_card_count_and_provider(...)
```

или:

```python
hand_activity.invalidate_generated_groups()
```

Тогда декоратор не будет знать, как именно очищаются группы.

---

## 9. Если список карт не изменился, `set_cards()` ничего не делает

### Поведение

```python
if next_keys == self.card_resource_keys:
    return
```

### Почему это нормально

Это защищает от лишней пересборки.

### Потенциальная проблема

Если ресурсы в `resource_manager` были перезагружены, но ключи остались теми же, группы не пересоздадутся.

### Рекомендация

Если в проекте бывает hot reload ресурсов, добавить параметр:

```python
def set_cards(self, cards, force=False):
    ...
    if not force and next_keys == self.card_resource_keys:
        return
```

---

## 10. `apply_fixture()` удаляет `resource_key` из fixture

### Проблема

Метод:

```python
decorated_fixture = dict(fixture)
decorated_fixture["card_count"] = len(self.card_resource_keys)
decorated_fixture.pop("resource_key", None)
self.hand_activity.apply_fixture(decorated_fixture)
```

### Почему это логично

Декоратор сам управляет ресурсами карт, поэтому не даёт wrapped activity использовать один общий `resource_key`.

### Потенциальная проблема

Если wrapped activity ожидает `resource_key` для других целей, он будет silently удалён.

### Рекомендация

Это поведение стоит явно описать в docstring:

```text
resource_key intentionally ignored because visible card resources are controlled by this decorator.
```

---

## 11. `apply_fixture()` форсирует `card_count`

### Поведение

```python
decorated_fixture["card_count"] = len(self.card_resource_keys)
```

### Почему это логично

Количество generated cards должно соответствовать списку видимых карт.

### Потенциальная проблема

Если fixture одновременно содержит:

```python
cards_from_manifest = True
card_count = 5
```

то `card_count` используется как slice-size в `get_fixture_slice_bounds()`, а затем перезаписывается для hand activity.

Это нормально, но поведение многоступенчатое и не сразу очевидно.

### Рекомендация

Добавить комментарий:

```python
# card_count in visible decorator means requested card list length;
# card_count passed to hand activity is derived from resolved resource keys.
```

---

## 12. `cards_from_manifest` делает порядок карт зависимым от runtime cache

### Проблема

Метод:

```python
resource_keys = tuple(
    key
    for key in self.resource_manager.get_runtime_cache()
    if key.startswith("cards.") and key != "cards.card_back"
)
```

Порядок зависит от порядка ключей в runtime cache.

### Почему это опасно

Если runtime cache — dict, порядок обычно стабилен в рамках insertion order, но он может зависеть от порядка загрузки ресурсов.

Для debug это допустимо, но для воспроизводимых fixture лучше иметь сортировку.

### Рекомендация

Сортировать ключи:

```python
resource_keys = tuple(sorted(
    key
    for key in self.resource_manager.get_runtime_cache()
    if key.startswith("cards.") and key != "cards.card_back"
))
```

---

## 13. `cards_from_manifest` silently возвращает пустой список без `resource_manager`

### Проблема

```python
if self.resource_manager is None:
    return ()
```

### Почему это может быть нормально

Это безопасно: нет resource manager — нет карт.

### Почему это может быть проблемой

Если fixture явно запросил `cards_from_manifest`, но `resource_manager` не передан, ошибка конфигурации будет скрыта.

### Рекомендация

Для debug-режима можно оставить.

Для строгого режима лучше падать явно:

```python
raise RuntimeError("cards_from_manifest requires resource_manager")
```

Или хотя бы логировать warning.

---

## 14. `normalize_cards()` молча игнорирует неподдерживаемые элементы

### Проблема

Метод принимает:

```python
str
dict with resource_key/key
```

А всё остальное игнорирует.

```python
for card in cards or ():
    if isinstance(card, str):
        normalized.append(card)
    elif isinstance(card, dict):
        resource_key = card.get("resource_key") or card.get("key")
        if resource_key:
            normalized.append(str(resource_key))
```

### Почему это опасно

Если в список попадёт неправильный объект, например игровая карта без `resource_key`, она просто исчезнет из руки.

Симптом:

```text
controller отправил 6 карт
decorator показал 4 карты
ошибки нет
```

### Рекомендация

Добавить strict mode или хотя бы явную ошибку для неподдерживаемых элементов.

Например:

```python
else:
    raise TypeError(f"Unsupported card descriptor: {card!r}")
```

Для dev-fixture можно оставить мягкое поведение, но тогда стоит логировать ignored entries.

---

## 15. `normalize_cards()` не поддерживает реальные card-модели

### Проблема

Docstring говорит, что позже Controller должен предоставлять реальные карты. Но `normalize_cards()` сейчас поддерживает только:

```text
string resource key
dict with resource_key/key
```

Если Controller будет передавать domain object:

```python
Card(suit="clubs", rank="6")
```

он будет проигнорирован.

### Рекомендация

Заранее определить boundary-format между Controller и view:

```text
Controller передаёт card_id, а view сама маппит card_id -> resource_key
```

или:

```text
Controller передаёт view model: {"card_id": ..., "resource_key": ...}
```

Для визуального слоя лучше принимать именно view model, а не domain object.

---

## 16. `get_card_resource_key()` бросает RuntimeError только при выходе за диапазон

### Поведение

```python
try:
    return self.card_resource_keys[index]
except IndexError as error:
    raise RuntimeError("VisibleCardsHandDecorator card index is out of range") from error
```

### Почему это нормально

Ошибка становится понятнее, чем обычный `IndexError`.

### Потенциальная проблема

Если `index` отрицательный, Python вернёт элемент с конца списка, а ошибки не будет.

Например:

```python
index = -1
```

вернёт последнюю карту.

### Рекомендация

Проверять индекс явно:

```python
if index < 0 or index >= len(self.card_resource_keys):
    raise RuntimeError("VisibleCardsHandDecorator card index is out of range")
return self.card_resource_keys[index]
```

---

## 17. `limit_cards()` silently обрезает список

### Проблема

```python
return tuple(cards)[: max(0, int(self.max_cards))]
```

Если `max_cards=2`, а передано 5 карт, три карты будут молча отброшены.

### Почему это может быть нормально

Для слота на столе с максимумом 2 карты это удобно.

### Почему это может быть опасно

Для руки игрока silent truncation может скрыть ошибку логики.

### Рекомендация

Добавить комментарий в docstring или strict option:

```python
if self.strict_max_cards and len(cards) > self.max_cards:
    raise ValueError("Too many cards")
```

---

## 18. `max_cards` может быть отрицательным или некорректным

### Проблема

В `limit_cards()`:

```python
max(0, int(self.max_cards))
```

Отрицательные значения превращаются в `0`, а некорректная строка вызовет `ValueError`.

### Почему это может быть нормально

`max(0, ...)` защищает от отрицательных значений.

### Потенциальная проблема

Если `max_cards=-1`, все карты исчезнут, хотя это скорее ошибка конфигурации.

### Рекомендация

Валидировать `max_cards` в `__init__`:

```python
if max_cards is not None:
    max_cards = int(max_cards)
    if max_cards < 0:
        raise ValueError("max_cards must be non-negative")
self.max_cards = max_cards
```

---

## 19. `normalize_slice()` может сломаться на строке

### Проблема

Если `card_slice` — строка, например `"0:5"`, метод попадёт в ветку:

```python
values = tuple(card_slice)
start = values[0]
stop = values[1]
```

То есть получит символы `"0"` и `":"`, а `int(":")` упадёт.

### Рекомендация

Проверять тип:

```python
if not isinstance(card_slice, (tuple, list)):
    raise TypeError("card_slice must be dict, tuple or list")
```

---

## 20. `normalize_slice()` не валидирует отрицательные значения

### Проблема

Сейчас можно получить:

```python
start = -5
stop = -1
```

Python slicing это поддерживает, но для debug fixture это может быть неожиданно.

### Рекомендация

Решить, нужны ли отрицательные индексы.

Если нет:

```python
start = max(0, start)
if stop is not None:
    stop = max(start, stop)
```

Если да — задокументировать поддержку negative slicing.

---

## 21. `get_fixture_slice_bounds()` меняет смысл `card_count`

### Проблема

В методе:

```python
if "card_count" in fixture:
    count = max(0, int(fixture["card_count"]))
    stop = start + count
```

Здесь `card_count` означает “сколько карт взять из manifest”.

Но в `apply_fixture()` затем:

```python
decorated_fixture["card_count"] = len(self.card_resource_keys)
```

Для wrapped hand activity `card_count` означает “сколько generated groups создать”.

### Почему это может запутывать

Один и тот же ключ `card_count` используется на двух разных уровнях с близким, но не полностью одинаковым смыслом.

### Рекомендация

Для manifest debug-режима использовать отдельный ключ:

```python
manifest_card_count
```

или явно описать двухступенчатое поведение.

---

## 22. `draw()` без проверки вызывает `hand_activity.draw(screen)`

### Проблема

```python
def draw(self, screen):
    self.hand_activity.draw(screen)
```

Если wrapped activity не имеет `draw`, будет ошибка.

### Почему это может быть нормально

Для hand activity draw, скорее всего, обязательный.

### Рекомендация

Если draw обязателен — добавить это в интерфейс/валидацию.

Если draw опционален — использовать `hasattr`, как в других Activity.

---

## 23. Нет type hints

### Проблема

Методы не аннотированы:

```python
def __init__(self, hand_activity, cards=None, resource_manager=None, max_cards=None):
def normalize_cards(cards):
def normalize_slice(card_slice):
```

### Почему это опасно

Класс является adapter/decorator на границе controller data и visual activity. Здесь особенно важно понимать типы входных данных.

### Рекомендация

Добавить type hints или Protocol:

```python
def normalize_cards(cards) -> tuple[str, ...]:
    ...

def limit_cards(self, cards: tuple[str, ...]) -> tuple[str, ...]:
    ...
```

Для `hand_activity` можно использовать Protocol.

---

# Приоритет исправлений

## Высокий приоритет

1. Явно определить, владеет ли декоратор `hand_activity`.
2. Добавить lazy-start в `update()` или задокументировать, почему декоратор не имеет собственного lifecycle.
3. После `set_cards()` пересинхронизировать generated groups/layout, если activity уже started.
4. Исправить `is_finished()`, чтобы он учитывал `_finished` самого декоратора.
5. Добавить явный формат данных от Controller: `resource_key`, `card_id`, `view model` или другой стабильный контракт.

## Средний приоритет

6. Добавить валидацию совместимости `hand_activity`.
7. Сделать `get_card_resource_key()` устойчивым к отрицательным индексам.
8. Решить, должен ли `normalize_cards()` молча игнорировать плохие элементы.
9. Сортировать manifest-карты для воспроизводимого debug-поведения.
10. Валидировать `max_cards` в `__init__`.

## Низкий приоритет

11. Добавить type hints.
12. Документировать, что `resource_key` удаляется из fixture намеренно.
13. Разделить `card_count` для manifest-slice и `card_count` для generated groups.
14. Проверить и задокументировать negative slicing в `normalize_slice()`.
15. Добавить optional `force=True` в `set_cards()` для hot reload ресурсов.

---

# Главный вывод

`VisibleCardsHandDecorator` — полезный адаптер между списком видимых карт и hand fan activity, но сейчас он слишком глубоко мутирует wrapped activity:

```python
self.hand_activity.card_resource_provider = self.get_card_resource_key
self.hand_activity.card_layer_name = "card"
self.hand_activity.card_count = len(self.card_resource_keys)
```

Это допустимо, если декоратор получает эксклюзивное владение `hand_activity`.

Главный риск — смена карт через `set_cards()`:

```python
self.hand_activity.clear_generated_groups()
self.card_resource_keys = next_keys
self.hand_activity.card_count = len(self.card_resource_keys)
```

После очистки groups не пересоздаются немедленно. Если внешний код ожидает мгновенного визуального обновления, рука может временно или постоянно остаться пустой до следующего явного layout/sync вызова.

Перед интеграцией с реальным `GameController` стоит определить устойчивый формат данных:

```text
Controller sends domain state
-> View adapter maps domain cards to resource keys
-> VisibleCardsHandDecorator updates visual resources
-> hand_activity rebuilds/syncs generated groups
```

Так декоратор останется визуальным адаптером, а не начнёт зависеть от случайной формы игровых объектов.
