# Отчёт о проблемах в `cards_slot_activity.py`

**Предложенное имя файла:** `cards_slot_activity_audit_report.md`

## Контекст

Файл содержит `CardsSlotActivityDecorator` — декоратор для центрального слота/игровой области стола. Он наследуется от `VisibleCardsHandDecorator`, ограничивает количество карт до `max_cards=2`, а затем нормализует локальные координаты сгенерированных групп так, чтобы содержимое слота начиналось с `(0, 0)`.

Основная идея класса:

```text
hand_activity создаёт/раскладывает visible cards
-> CardsSlotActivityDecorator считает bounds этих групп
-> сдвигает группы так, чтобы общий bounds начинался с нуля
-> сохраняет slot_content_rect как размер занятой области
```

Код короткий, но в нём есть несколько важных рисков, связанных с координатными системами, масштабом и зависимостью от внутреннего состояния `hand_activity`.

---

## 1. Класс напрямую обращается к `self.hand_activity.generated_groups`

### Проблема

В нескольких местах используется прямой доступ:

```python
for group in self.hand_activity.generated_groups:
```

Это происходит в:

- `normalize_slot_content()`;
- `calculate_generated_groups_bounds()`.

### Почему это опасно

`CardsSlotActivityDecorator` наследуется от `VisibleCardsHandDecorator`, но вместо публичного API использует внутреннее поле вложенной `hand_activity`.

Если в будущем `hand_activity`:

- переименует `generated_groups`;
- начнёт хранить группы в другом месте;
- будет лениво генерировать группы;
- станет возвращать не список, а другой контейнер;
- будет иметь generated-группы, которыми владеет не только слот;

то этот декоратор сломается.

### Рекомендация

Сделать явный метод доступа на уровне базового декоратора или hand activity:

```python
def iter_generated_groups(self):
    return tuple(self.hand_activity.generated_groups)
```

И использовать его:

```python
for group in self.iter_generated_groups():
    ...
```

Так зависимость будет централизована.

---

## 2. Нет проверки, что `hand_activity` имеет `generated_groups`

### Проблема

Код безусловно ожидает:

```python
self.hand_activity.generated_groups
```

### Почему это опасно

Если в конструктор случайно передать несовместимый `hand_activity`, ошибка появится не сразу, а при вызове `apply_fixture()` или `normalize_slot_content()`.

### Рекомендация

Добавить раннюю валидацию в `__init__` или использовать безопасный accessor.

Пример:

```python
if not hasattr(hand_activity, "generated_groups"):
    raise ValueError("CardsSlotActivityDecorator requires hand_activity.generated_groups")
```

Но ещё лучше — проверять не поле, а публичный интерфейс.

---

## 3. `normalize_slot_content()` смешивает scaled bounds и unscaled position

### Проблема

Границы считаются через:

```python
rect = self.get_group_slot_rect(group)
```

А `get_group_slot_rect()` может вернуть scaled rect:

```python
if hasattr(group, "get_scaled_local_rect"):
    return group.get_scaled_local_rect()
return group.local_rect
```

Но сдвиг группы выполняется через `group.local_rect`:

```python
rect = group.local_rect
group.set_local_position(rect.x - bounds.x, rect.y - bounds.y)
```

### Почему это опасно

Если `bounds` рассчитан в scaled-координатах, а `group.local_rect` находится в unscaled/local-координатах, то вычитание `bounds.x` и `bounds.y` может быть некорректным.

Симптомы:

- группы смещаются слишком сильно или слишком слабо;
- `slot_content_rect` не совпадает с фактической визуальной областью;
- при scale factor, отличном от `1.0`, слот начинает “ползти”;
- external layout получает неверный размер.

### Рекомендация

Выбрать одну координатную систему для всего метода.

Вариант A: всё считать и двигать в local/unscaled coordinates.

Вариант B: всё считать в scaled coordinates, но тогда `set_local_position()` должен получать координаты после обратной конвертации.

Самое безопасное решение — явно назвать методы:

```python
calculate_generated_groups_local_bounds()
calculate_generated_groups_scaled_bounds()
```

И не смешивать их.

---

## 4. `slot_content_rect` может отражать scaled bounds, а группы сдвигаются по local bounds

### Проблема

После нормализации устанавливается:

```python
self.slot_content_rect = pygame.Rect(0, 0, bounds.width, bounds.height)
```

Но `bounds` может быть scaled, если у группы есть `get_scaled_local_rect()`.

### Почему это опасно

Название `slot_content_rect` не говорит, в какой системе координат находится rect:

- local coordinates;
- scaled local coordinates;
- screen coordinates;
- layout coordinates.

Если внешний layout-модуль ожидает local rect, а получает scaled rect, размер слота будет неправильным.

### Рекомендация

Документировать контракт:

```python
def get_slot_content_rect(self):
    # Return slot content rect in scaled local coordinates.
    ...
```

Или переименовать поле:

```python
self.slot_content_scaled_rect
```

Если нужен именно local rect — считать bounds только по `group.local_rect`.

---

## 5. `normalize_slot_content()` меняет позиции групп после layout базовой hand activity

### Проблема

`apply_fixture()` делает:

```python
super().apply_fixture(fixture)
self.normalize_slot_content()
```

То есть сначала базовый декоратор/hand activity применяет fixture и раскладывает карты, а затем `CardsSlotActivityDecorator` вручную сдвигает группы.

### Почему это опасно

Если `VisibleCardsHandDecorator` или вложенная `hand_activity` после этого снова пересчитает layout, нормализация будет потеряна.

Например:

```text
apply_fixture()
-> normalize_slot_content()
-> update()
-> hand_activity.apply_fan_layout()
-> группы снова уезжают в исходные позиции
```

Это зависит от реализации `VisibleCardsHandDecorator` и `hand_activity`.

### Рекомендация

Проверить, где именно вызывается layout-пересчёт.

Если layout может обновляться не только в `apply_fixture()`, нормализацию нужно вызывать после каждого такого обновления. Например:

```python
def update(self, dt):
    super().update(dt)
    if self.layout_dirty:
        self.normalize_slot_content()
```

Или сделать нормализацию частью layout pipeline, а не отдельной пост-операцией.

---

## 6. Нет override `update()`, поэтому нормализация может устаревать

### Проблема

Файл переопределяет только:

```python
apply_fixture()
```

Но не переопределяет `update()`.

### Почему это опасно

Если карты меняются не через fixture, а через обычные runtime-команды, например:

- добавление карты на стол;
- удаление карты со стола;
- смена visible cards;
- пересчёт scale;
- resize frame;
- изменение layout;

то `slot_content_rect` может остаться старым.

### Рекомендация

Добавить механизм dirty-обновления.

Простой вариант:

```python
def update(self, dt):
    super().update(dt)
    self.normalize_slot_content()
```

Но это может быть избыточно каждый кадр.

Лучше:

```python
def update(self, dt):
    super().update(dt)
    if self.needs_slot_normalization:
        self.normalize_slot_content()
        self.needs_slot_normalization = False
```

---

## 7. `slot_content_rect` сбрасывается в `(0, 0, 0, 0)` при отсутствии групп

### Поведение

Если bounds нет:

```python
self.slot_content_rect = pygame.Rect(0, 0, 0, 0)
return
```

### Почему это может быть нормально

Если в слоте нет карт, занятая область действительно пустая.

### Потенциальная проблема

Внешний layout может ожидать не “занятую область”, а “размер слота”. Тогда пустой rect `0x0` может схлопнуть layout.

Например центральный слот стола может иметь фиксированную область даже без карт.

### Рекомендация

Разделить два понятия:

```text
slot_area_rect      — доступная область слота
slot_content_rect   — фактически занятая область карт
```

Сейчас `slot_content_rect` — именно content bounds, а не размер самого слота. Это стоит явно указать в docstring.

---

## 8. `get_slot_content_rect()` возвращает copy, но сам rect обновляется только вручную

### Хорошо

Метод делает:

```python
return self.slot_content_rect.copy()
```

Это правильно: внешний код не может случайно изменить внутренний rect.

### Риск

Сам `slot_content_rect` обновляется только при `normalize_slot_content()`, а она вызывается только из `apply_fixture()`.

То есть copy защищает от мутации, но не от устаревшего значения.

### Рекомендация

Либо гарантировать, что `normalize_slot_content()` вызывается после каждого layout-изменения, либо вычислять rect лениво:

```python
def get_slot_content_rect(self):
    self.normalize_slot_content()
    return self.slot_content_rect.copy()
```

Минус ленивого варианта: getter начнёт менять позиции групп, что может быть неожиданным side effect.

---

## 9. `normalize_slot_content()` имеет side effect, но по имени это не сразу очевидно

### Проблема

Название звучит как безопасная нормализация внутреннего состояния, но метод фактически двигает visual groups:

```python
group.set_local_position(...)
self.hand_activity.frame.group_origins[group.id] = group.local_rect.topleft
```

### Почему это опасно

Вызов метода меняет layout.

Если другой разработчик вызовет его просто чтобы “обновить размеры”, он также изменит позиции групп.

### Рекомендация

Переименовать метод более явно:

```python
normalize_generated_groups_to_slot_origin()
```

или:

```python
move_generated_groups_to_slot_origin()
```

А расчёт bounds держать отдельно.

---

## 10. Прямое обновление `frame.group_origins`

### Проблема

После перемещения группы код вручную обновляет:

```python
self.hand_activity.frame.group_origins[group.id] = group.local_rect.topleft
```

### Почему это опасно

Это нарушает инкапсуляцию `Frame`.

Если `Frame` должен сам знать, когда группа перемещается, прямое изменение `group_origins` может обойти другую важную логику:

- dirty flags;
- кэш layout;
- z-order;
- collision cache;
- debug overlay;
- history для анимаций.

### Рекомендация

Лучше иметь метод на `Frame` или `Group`, который перемещает группу и синхронизирует origin:

```python
self.hand_activity.frame.set_group_origin(group.id, group.local_rect.topleft)
```

или:

```python
group.set_local_position(...)
group.sync_origin_with_parent_frame()
```

Если такого API нет — стоит добавить.

---

## 11. Нет проверки наличия `frame` у `hand_activity`

### Проблема

Код ожидает:

```python
self.hand_activity.frame.group_origins
```

### Почему это опасно

`hand_activity` может иметь `generated_groups`, но не иметь `frame`, или `frame` может не иметь `group_origins`.

Тогда ошибка будет runtime-only.

### Рекомендация

Добавить валидацию или безопасный helper:

```python
frame = getattr(self.hand_activity, "frame", None)
if frame is None or not hasattr(frame, "group_origins"):
    raise ValueError("CardsSlotActivityDecorator requires hand_activity.frame.group_origins")
```

---

## 12. `max_cards=2` жёстко зашит в конструктор

### Проблема

Конструктор всегда передаёт:

```python
max_cards=2
```

### Почему это может быть нормально

Если это именно слот центральной области для двух карт — например “карта атаки + карта защиты” — это логично.

### Почему это может стать проблемой

Если позже появятся другие режимы стола:

- несколько карт;
- комбо;
- сброс;
- временные эффекты;
- ряд карт на столе;

придётся создавать новый класс или менять этот.

### Рекомендация

Если ограничение действительно доменное — оставить и добавить комментарий.

Если это временный dev-лимит — сделать параметром:

```python
def __init__(self, hand_activity, cards=None, resource_manager=None, max_cards=2):
    super().__init__(..., max_cards=max_cards)
```

---

## 13. Нет явного контракта для `cards`

### Проблема

Конструктор принимает:

```python
cards=None
```

и передаёт дальше в `VisibleCardsHandDecorator`.

Но в этом файле не видно, что такое `cards`:

- список resource keys;
- список card DTO;
- список игровых карт;
- список visual descriptors.

### Почему это опасно

Класс называется `CardsSlotActivityDecorator`, а комментарий говорит:

```text
Controller will provide real table cards
```

Это намекает на будущую интеграцию с контроллером, где тип `cards` станет важен.

### Рекомендация

Добавить docstring к `__init__` или type hints:

```python
def __init__(
    self,
    hand_activity,
    cards: list[str] | None = None,
    resource_manager=None,
):
    ...
```

Если `cards` — не строки, указать настоящий тип.

---

## 14. `get_group_slot_rect()` возвращает оригинальный `group.local_rect` без copy

### Проблема

Если у группы нет `get_scaled_local_rect()`, метод возвращает:

```python
return group.local_rect
```

### Почему это может быть опасно

Если `group.local_rect` — mutable `pygame.Rect`, вызывающий код может случайно изменить его.

В текущем коде `calculate_generated_groups_bounds()` делает:

```python
bounds = rect.copy() if bounds is None else bounds.union(rect)
```

То есть прямо сейчас rect не мутируется.

Но сам helper потенциально опасен для будущего использования.

### Рекомендация

Возвращать copy:

```python
return group.local_rect.copy()
```

И для scaled rect тоже желательно убедиться, что возвращается независимый rect.

---

## 15. Bounds считаются до перемещения, но не пересчитываются после перемещения

### Поведение

`normalize_slot_content()`:

1. считает `bounds`;
2. двигает группы на `-bounds.x`, `-bounds.y`;
3. ставит `slot_content_rect = Rect(0, 0, bounds.width, bounds.height)`.

Это нормально, если перемещение — чистый перенос всех групп на одинаковый offset.

### Потенциальная проблема

Если `group.set_local_position()` меняет масштаб, hit rect, local rect или вызывает дополнительные side effects, итоговые bounds могут отличаться от исходных.

### Рекомендация

Если `set_local_position()` простой — ничего менять не нужно.

Если нет — после перемещения лучше пересчитать bounds или хотя бы покрыть это тестом.

---

## 16. Отсутствуют type hints

### Проблема

Файл маленький, но он работает на стыке нескольких объектов:

- `hand_activity`;
- `cards`;
- `resource_manager`;
- `pygame.Rect`;
- `Group`;
- `VisibleCardsHandDecorator`.

Без type hints трудно понять ожидаемые интерфейсы.

### Рекомендация

Добавить минимальные type hints там, где это не создаёт циклических импортов:

```python
def get_slot_content_rect(self) -> pygame.Rect:
    ...

def calculate_generated_groups_bounds(self) -> pygame.Rect | None:
    ...
```

Для `hand_activity` можно использовать Protocol, если классы ещё нестабильны.

---

# Приоритет исправлений

## Высокий приоритет

1. Разобраться, в какой системе координат находится `slot_content_rect`.
2. Убрать смешение `get_scaled_local_rect()` и `group.local_rect` в `normalize_slot_content()`.
3. Проверить, не устаревает ли нормализация после `update()` или runtime-изменения карт.
4. Избежать прямой зависимости от `self.hand_activity.generated_groups`, если это внутреннее поле.

## Средний приоритет

5. Заменить прямое обновление `frame.group_origins` на публичный метод.
6. Добавить проверку совместимости `hand_activity`.
7. Разделить понятия “размер слота” и “занятая картами область”.
8. Явно описать контракт `cards`.

## Низкий приоритет

9. Сделать `max_cards` параметром, если ограничение временное.
10. Возвращать copy из `get_group_slot_rect()`.
11. Добавить type hints.
12. Переименовать `normalize_slot_content()` в более явное имя.

---

# Главный вывод

Главная проблема файла — не в количестве кода, а в неявной координатной системе.

Особенно подозрительный участок:

```python
bounds = self.calculate_generated_groups_bounds()

for group in self.hand_activity.generated_groups:
    rect = group.local_rect
    group.set_local_position(rect.x - bounds.x, rect.y - bounds.y)
```

`bounds` может быть рассчитан через `get_scaled_local_rect()`, а позиция берётся из `group.local_rect`.

Если scaled rect и local rect отличаются, нормализация будет математически некорректной.

Перед развитием этого класса стоит явно решить:

```text
slot_content_rect хранится в local coordinates
или
slot_content_rect хранится в scaled local coordinates
или
slot_content_rect хранится в screen/layout coordinates
```

После этого весь метод `normalize_slot_content()` нужно привести к одной выбранной системе координат.
