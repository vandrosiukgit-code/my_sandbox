# Отчёт о проблемах в `play_area_slots_activity.py`

**Предложенное имя файла:** `play_area_slots_activity_audit_report.md`

## Контекст

Файл содержит `PlayAreaSlotsActivity` — Activity, которая управляет размещением временных frame-копий карточных слотов внутри `play_area_frame`.

По смыслу класс делает несколько вещей одновременно:

```text
prototype_slot_frame
-> копирование/создание дополнительных slot frames
-> создание CardsSlotActivity для каждого slot frame
-> применение общего fixture к каждому slot activity
-> расчёт размеров слота
-> расчёт layout-центра и шага
-> размещение slot frames внутри play_area_frame
-> удаление лишних frames и activities
```

Класс полезен как dev-инструмент для настройки центральной игровой области, но в нём есть несколько серьёзных рисков: смешение ответственности, неявное владение prototype-объектами, возможная рассинхронизация activity/frame registry и layout, завязанный на конкретные id игроков.

---

## 1. `update()` не обновляет layout после старта

### Проблема

Метод `update()` только запускает activity, если она ещё не стартовала:

```python
def update(self, dt):
    _ = dt
    if not self.started:
        self.start()
```

Но `apply_layout()` вызывается только из `apply_fixture()`.

### Почему это опасно

Если после применения fixture изменится что-то важное:

- размер `play_area_frame`;
- размер prototype slot frame;
- размер slot content;
- положение left/right player hands;
- количество карт внутри слота;
- scale factor slot activity;
- screen resize;
- layout родительских frames;

то `PlayAreaSlotsActivity` не пересчитает позиции автоматически.

### Рекомендация

Добавить dirty-флаг или layout signature.

Пример:

```python
def update(self, dt):
    if not self.started:
        self.start()

    signature = self.get_layout_signature()
    if signature != self._last_layout_signature:
        self.apply_layout()
        self._last_layout_signature = signature
```

Важно не вызывать `apply_layout()` каждый кадр без необходимости, потому что он может пересоздавать frames/activities и применять fixtures.

---

## 2. `start()` не переопределён и не вызывает `apply_layout()`

### Проблема

Класс наследуется от `Activity`, но не имеет собственного `start()`.

Если activity добавили на экран и начали обновлять без предварительного `apply_fixture()`, layout не будет применён.

По умолчанию в `__init__`:

```python
self.slot_count = 1
self.managed_slot_ids = [self.prototype_slot_frame.id]
```

Но позиционирование slot frame через `apply_layout()` не произойдёт.

### Почему это опасно

Activity может считаться запущенной, но не применить свой layout.

### Рекомендация

Добавить:

```python
def start(self):
    super().start()
    self.apply_layout()
```

Если layout должен применяться только после fixture, тогда это нужно явно задокументировать.

---

## 3. `apply_fixture()` полностью заменяет `slot_activity_fixture`

### Проблема

Сейчас:

```python
self.slot_activity_fixture = dict(
    fixture.get("slot_activity", self.DEFAULT_SLOT_ACTIVITY_FIXTURE)
)
```

Если fixture содержит частичный `slot_activity`, например только:

```python
{
    "slot_activity": {
        "scale_factor": 0.8
    }
}
```

то поля по умолчанию будут потеряны:

```python
"cards"
"radius"
"center_offset"
```

### Почему это опасно

Частичный fixture может неожиданно очистить содержимое слота или изменить поведение вложенной activity.

### Рекомендация

Мержить с дефолтом:

```python
slot_activity_fixture = dict(self.DEFAULT_SLOT_ACTIVITY_FIXTURE)
slot_activity_fixture.update(fixture.get("slot_activity", {}))
self.slot_activity_fixture = slot_activity_fixture
```

---

## 4. `DEFAULT_SLOT_ACTIVITY_FIXTURE` содержит tuple, но копируется через `dict()`

### Проблема

В дефолтном fixture:

```python
DEFAULT_SLOT_ACTIVITY_FIXTURE = {
    "cards": (
        "cards.6_of_clubs",
        "cards.7_of_clubs",
    ),
    ...
}
```

Копирование через `dict()` достаточно для верхнего уровня, но это shallow copy.

### Почему это сейчас не критично

`cards` — tuple, он immutable.

### Почему стоит отметить

Если позже в fixture появятся вложенные mutable структуры, например список эффектов, настройки layers, offset-таблицы, shallow copy станет источником неожиданных shared mutations.

### Рекомендация

Если fixture останется простым — ничего менять не нужно.

Если fixture станет сложнее — использовать `copy.deepcopy()`.

---

## 5. Prototype slot activity применяется как обычная slot activity

### Проблема

В `__init__`:

```python
if self.prototype_slot_activity is not None:
    self.slot_activities[self.prototype_slot_frame.id] = self.prototype_slot_activity
```

А затем:

```python
for activity in self.slot_activities.values():
    if hasattr(activity, "apply_fixture"):
        activity.apply_fixture(self.slot_activity_fixture)
```

То есть prototype activity получает тот же fixture, что и все скопированные слоты.

### Почему это может быть нормально

Если prototype — это первый реальный слот, такое поведение логично.

### Почему это может быть опасно

Если prototype нужен только как шаблон, его состояние будет мутироваться как у обычного слота.

### Рекомендация

Явно определить роль prototype:

```text
prototype is first managed slot
```

или

```text
prototype is only a template and should not be mutated after cloning
```

Сейчас поведение ближе к первому варианту.

---

## 6. Удаление prototype activity намеренно пропускается, но frame всё равно остаётся managed

### Проблема

В `remove_slot_activity()`:

```python
activity = self.slot_activities.pop(frame_id, None)
if activity is None or activity is self.prototype_slot_activity:
    return
```

Если `slot_count` станет `0`, `ensure_slot_frames()` сформирует пустой `target_ids`. Затем для prototype id будет вызван `remove_slot_activity()`, который сделает `pop()`, но не завершит prototype activity, потому что это prototype.

После этого `managed_slot_ids` станет пустым.

### Почему это опасно

Может возникнуть рассинхронизация:

- prototype frame физически остаётся на экране, потому что `remove_slot_frame()` не удаляет prototype;
- prototype activity не завершена;
- но `managed_slot_ids` больше не содержит prototype id;
- `slot_activities` больше не содержит prototype activity, потому что `pop()` уже произошёл.

### Рекомендация

Для prototype activity не делать `pop()`, если она не должна удаляться.

Например:

```python
if activity is self.prototype_slot_activity:
    return
```

нужно проверять до `pop()`.

Или при `slot_count = 0` отдельно скрывать prototype frame/activity, а не частично удалять из registry.

---

## 7. `slot_count = 0` обработан неоднозначно

### Проблема

`apply_fixture()` допускает:

```python
self.slot_count = max(0, int(fixture.get("slot_count", self.slot_count)))
```

То есть ноль разрешён.

Но `remove_slot_frame()` не удаляет prototype:

```python
if frame_id == self.prototype_slot_frame.id:
    return
```

### Почему это опасно

Если `slot_count = 0`, ожидается отсутствие всех слотов. Но prototype frame не удаляется.

Возможные эффекты:

- слот визуально остаётся;
- prototype activity продолжает жить;
- `managed_slot_ids` пустой, но frame всё ещё есть в `screen.screen_frames`;
- повторное увеличение `slot_count` может работать непредсказуемо, если activity была удалена из `slot_activities`.

### Рекомендация

Определить семантику:

- `slot_count = 0` означает “скрыть все слоты”;
- или `slot_count` должен быть минимум `1`.

Если минимум `1`, заменить:

```python
self.slot_count = max(1, int(...))
```

Если ноль разрешён, добавить корректное скрытие prototype frame/activity.

---

## 8. `remove_slot_frame()` напрямую мутирует внутренние структуры

### Проблема

Удаление frame происходит так:

```python
self.play_area_frame.child_frames.pop(frame_id, None)
self.screen.screen_frames.pop(frame_id, None)
```

### Почему это опасно

Это обходит возможную внутреннюю логику `screen` и `frame`:

- unlink parent/child;
- invalidation layout cache;
- очистка input/collision state;
- debug registry;
- z-order;
- callbacks;
- active animations.

### Рекомендация

Лучше иметь публичный API:

```python
self.screen.remove_frame(frame_id)
```

или:

```python
self.play_area_frame.remove_child_frame(frame_id)
```

Если такого API нет, стоит добавить.

---

## 9. `remove_slot_activity()` напрямую удаляет activity из `screen.active_activities`

### Проблема

Код делает:

```python
if activity in self.screen.active_activities:
    self.screen.active_activities.remove(activity)
```

### Почему это опасно

Это тоже обходит возможный lifecycle screen manager:

- finish hooks;
- deferred removal;
- iteration safety;
- activity ordering;
- debug state.

Если `remove_slot_activity()` вызовется во время итерации по `active_activities`, прямой `remove()` может привести к пропуску следующей activity или другим трудноуловимым багам.

### Рекомендация

Сделать публичный метод:

```python
self.screen.remove_activity(activity)
```

или deferred removal queue.

---

## 10. `screen.add_activity(activity)` вызывается без проверки дублей

### Проблема

В `ensure_slot_activities()`:

```python
self.screen.add_activity(activity)
```

Код проверяет только:

```python
if frame_id in self.slot_activities:
    continue
```

### Почему это может быть проблемой

Если `slot_activities` по какой-то причине рассинхронизировался с `screen.active_activities`, одна и та же activity может быть добавлена повторно или наоборот остаться активной без записи в `slot_activities`.

### Рекомендация

Публичный `screen.add_activity()` должен сам защищаться от дублей.

Если не защищается — добавить проверку.

---

## 11. Жёсткая зависимость от `screen.hand_activities`

### Проблема

Код использует:

```python
getattr(self.screen, "hand_activities", {}).get(activity_id)
...
self.screen.hand_activities[frame_id] = activity
...
self.screen.hand_activities.pop(frame_id, None)
```

### Почему это опасно

`hand_activities` используется как общий registry для разных типов activities:

- player hands;
- slot activities;
- возможно bot hand;
- возможно temporary table slots.

Это размывает смысл registry.

### Рекомендация

Разделить registry:

```python
screen.hand_activities
screen.slot_activities
screen.play_area_activities
```

Или использовать один общий `activity_registry`, но с понятными ключами и типами.

---

## 12. Layout зависит от жёстко заданных id игроков

### Проблема

`get_player_inner_horizontal_bounds()` использует конкретные id:

```python
left_rect = self.get_player_fan_or_frame_rect("left_player_hand", "left_player_frame")
right_rect = self.get_player_fan_or_frame_rect("right_player_hand", "right_player_frame")
```

### Почему это опасно

Activity становится привязанной к конкретному экрану и конкретной схеме имён.

Если id изменятся, layout silently fallback-нет на `content_rect.center`.

### Рекомендация

Передавать ids в конструктор или fixture:

```python
left_player_activity_id="left_player_hand"
left_player_frame_id="left_player_frame"
right_player_activity_id="right_player_hand"
right_player_frame_id="right_player_frame"
```

---

## 13. Смешение координат screen rect и play-area local rect

### Проблема

`get_player_fan_or_frame_rect()` возвращает:

```python
fan_rect = activity.calculate_fan_rect()
...
return self.screen.get_screen_frame(frame_id).rect
```

Затем в `get_player_inner_horizontal_bounds()` эти rect конвертируются так:

```python
left_inner_x = self.play_area_frame.to_local((left_rect.right, 0))[0]
right_inner_x = self.play_area_frame.to_local((right_rect.left, 0))[0]
```

### Почему это опасно

Корректность зависит от того, что `left_rect` и `right_rect` находятся в screen coordinates.

Но у некоторых activity `calculate_fan_rect()` может возвращать local rect, а не screen rect.

Если `calculate_fan_rect()` возвращает local coordinates, конвертация через `play_area_frame.to_local()` будет неверной.

### Рекомендация

Жёстко зафиксировать контракт:

```text
calculate_fan_rect() returns screen-space rect
```

или переименовать:

```python
calculate_fan_screen_rect()
```

Если contract нельзя гарантировать, сделать adapter, который явно приводит rect к screen coordinates.

---

## 14. В `to_local()` передаётся y = 0

### Проблема

Координаты конвертируются так:

```python
self.play_area_frame.to_local((left_rect.right, 0))[0]
```

Используется только `x`, поэтому `y=0` кажется безвредным.

### Почему это может стать проблемой

Если `to_local()` учитывает не только смещение, но и трансформации:

- scale;
- rotation;
- nested transforms;
- non-uniform transforms;

то `x` может зависеть от `y`.

### Рекомендация

Если система координат всегда axis-aligned и без rotation — оставить.

Но более корректно использовать реальный y, например центр rect:

```python
self.play_area_frame.to_local((left_rect.right, left_rect.centery))[0]
```

---

## 15. `calculate_horizontal_slot_step()` может вернуть слишком маленький step

### Проблема

Метод:

```python
step = (available_width - slot_size[0]) / (max_offset - min_offset)
return max(1, int(round(step)))
```

Если `available_width < slot_size[0]`, step станет отрицательным, а затем будет превращён в `1`.

### Почему это опасно

Слоты почти полностью наложатся друг на друга, но код не сигнализирует о проблеме.

### Рекомендация

Явно обработать недостаток места:

```python
if available_width <= slot_size[0]:
    return int(slot_size[0] + self.spacing[0])
```

или вернуть минимальный разумный step.

---

## 16. `columns` читается из fixture, но не используется

### Проблема

В `apply_fixture()`:

```python
self.columns = max(1, int(fixture.get("columns", self.columns)))
```

Но дальше `self.columns` нигде не используется.

### Почему это опасно

Это вводит в заблуждение. Пользователь fixture может думать, что `columns` влияет на layout, но фактически нет.

### Рекомендация

Либо удалить `columns`, либо использовать его в `get_default_slot_offset()` / `generate_default_slot_offsets()`.

Например, если нужен grid layout:

```python
column = index % self.columns
row = index // self.columns
```

---

## 17. `get_center_out_offset()` не используется

### Проблема

В классе есть метод:

```python
@staticmethod
def get_center_out_offset(index):
    ...
```

Но текущий layout использует:

```python
generate_default_slot_offsets()
```

### Почему это опасно

Мёртвый код усложняет понимание: непонятно, какой алгоритм раскладки актуальный.

### Рекомендация

Удалить метод, если он больше не нужен.

Или заменить им текущую генерацию, если именно он должен быть источником offset-ов.

---

## 18. `normalize_pair()` не защищает от плохого input

### Проблема

Метод:

```python
@staticmethod
def normalize_pair(value):
    if isinstance(value, dict):
        return int(round(float(value.get("x", 0)))), int(round(float(value.get("y", 0))))
    return int(round(float(value[0]))), int(round(float(value[1])))
```

### Почему это опасно

Если `value`:

- `None`;
- пустой список;
- строка;
- число;
- список длиной 1;

метод упадёт с не очень понятной ошибкой.

### Рекомендация

Добавить явную валидацию:

```python
if not isinstance(value, (tuple, list)) or len(value) < 2:
    raise ValueError("Expected pair as dict/list/tuple")
```

---

## 19. `normalize_offsets()` не проверяет тип offsets

### Проблема

```python
return tuple(cls.normalize_pair(offset) for offset in offsets)
```

Если `offsets` случайно будет строкой, метод будет итерироваться по символам.

### Рекомендация

Проверить, что `offsets` — list/tuple:

```python
if not isinstance(offsets, (list, tuple)):
    raise ValueError("slot_offsets must be a list or tuple of pairs")
```

---

## 20. `slot_offsets` может быть короче `slot_count`

### Поведение

В `get_slot_offset()`:

```python
if self.slot_offsets is not None and index < len(self.slot_offsets):
    return self.slot_offsets[index]
return self.get_default_slot_offset(index)
```

### Почему это может быть нормально

Частичная override-таблица offset-ов удобна для debugging.

### Риск

Если пользователь fixture ожидает, что `slot_offsets` полностью задаёт layout, недостающие offsets будут silently generated.

### Рекомендация

Документировать это поведение:

```text
slot_offsets can override only first N slot positions; remaining slots use default layout.
```

Или добавить strict mode.

---

## 21. `get_prototype_slot_size()` зависит только от prototype activity

### Проблема

Размер всех слотов берётся так:

```python
if self.prototype_slot_activity is not None:
    content_rect = self.prototype_slot_activity.get_slot_content_rect()
    if content_rect.width > 0 and content_rect.height > 0:
        return content_rect.size
return self.prototype_slot_frame.local_rect.size
```

### Почему это опасно

Если скопированные slot activities имеют другой контент или scale, layout всё равно использует размер prototype.

Сейчас `apply_slot_activity_fixtures()` применяет одинаковый fixture ко всем activity, поэтому это допустимо.

Но если в будущем у каждого слота будет своё содержимое, размер prototype станет недостаточным.

### Рекомендация

Для одинаковых слотов оставить.

Для разных слотов — считать размеры всех slot activities и использовать max size или per-slot size.

---

## 22. Порядок операций в `apply_layout()` может быть дорогим и иметь side effects

### Проблема

`apply_layout()` делает:

```python
self.ensure_slot_frames()
self.ensure_slot_activities()
self.apply_slot_activity_fixtures()

slot_size = self.get_prototype_slot_size()
...
slot_frame.set_local_rect(...)
```

Каждый layout заново применяет fixture ко всем slot activities.

### Почему это опасно

Если `apply_layout()` начнёт вызываться часто, например при resize или dirty update, это может:

- пересоздавать visual groups внутри slot activities;
- сбрасывать анимации;
- вызывать лишние layout-пересчёты;
- быть дорогим по CPU.

### Рекомендация

Разделить операции:

```text
sync slots count
sync activities
apply slot fixtures only if fixture changed
recalculate frame positions
```

---

## 23. После изменения размера slot frame вложенная activity может не знать о новом frame rect

### Проблема

В конце layout:

```python
slot_frame.set_local_rect((x, y, slot_size[0], slot_size[1]))
```

Но после изменения frame rect не вызывается явное обновление slot activity.

### Почему это может быть опасно

Если slot activity зависит от frame size/content rect, она может иметь устаревшие позиции карт.

### Рекомендация

После изменения frame rect можно пометить соответствующую slot activity dirty или вызвать её layout update.

Например:

```python
activity = self.slot_activities.get(frame_id)
if activity is not None and hasattr(activity, "apply_layout"):
    activity.apply_layout()
```

Но важно не зациклить layout.

---

## 24. Создание frame копирует только rect, но не визуальные свойства prototype

### Проблема

Новые frames создаются так:

```python
slot_frame = self.screen.create_frame(
    frame_id,
    rect=self.prototype_slot_frame.local_rect,
    parent_frame_id=self.play_area_frame.id,
)
```

Потом вызывается:

```python
slot_frame.set_rect_visibility(False)
```

### Почему это опасно

Если prototype frame имеет важные свойства:

- padding;
- anchor;
- background;
- border style;
- clipping;
- content rect;
- z-order;
- debug настройки;
- transform;
- custom flags;

они могут не скопироваться.

### Рекомендация

Сделать явный метод clone:

```python
slot_frame = self.screen.clone_frame(
    prototype_frame=self.prototype_slot_frame,
    new_id=frame_id,
    parent_frame_id=self.play_area_frame.id,
)
```

---

## 25. Нет type hints

### Проблема

Класс работает с большим количеством внешних объектов:

- `screen`;
- `play_area_frame`;
- `prototype_slot_frame`;
- `prototype_slot_activity`;
- `slot_activity_factory`;
- frame registry;
- activity registry;
- pygame-like Rect API.

Без type hints трудно понять контракт.

### Рекомендация

Добавить хотя бы возвращаемые типы для чистых helper-методов:

```python
def get_slot_frame_id(self, index: int) -> str:
    ...

def get_horizontal_offset_span(slot_offsets) -> tuple[int, int]:
    ...

def normalize_pair(value) -> tuple[int, int]:
    ...
```

Для `screen` и `frame` можно использовать Protocol, если реальные классы ещё часто меняются.

---

# Приоритет исправлений

## Высокий приоритет

1. Определить корректную семантику `slot_count = 0`.
2. Исправить `remove_slot_activity()`, чтобы prototype activity не выпадала из `slot_activities` при удалении.
3. Решить, должен ли `start()` вызывать `apply_layout()`.
4. Добавить dirty-пересчёт layout при изменении play area, player hands или slot content.
5. Убрать риск смешения screen/local координат в `get_player_inner_horizontal_bounds()`.

## Средний приоритет

6. Мержить `slot_activity_fixture` с дефолтом, а не заменять полностью.
7. Разделить `apply_layout()` на sync-count, sync-activity, apply-fixture и place-frames.
8. Заменить прямую мутацию `screen.screen_frames`, `child_frames` и `active_activities` на публичные методы.
9. Сделать ids player hands настраиваемыми.
10. Решить, нужен ли `columns`, и либо использовать его, либо удалить.

## Низкий приоритет

11. Удалить неиспользуемый `get_center_out_offset()`.
12. Добавить type hints.
13. Улучшить валидацию `normalize_pair()` и `normalize_offsets()`.
14. Документировать поведение частичных `slot_offsets`.
15. Сделать полноценное клонирование frame из prototype, если prototype имеет важные визуальные свойства.

---

# Главный вывод

Главная проблема файла — смешение dev-layout logic и управления жизненным циклом объектов.

`PlayAreaSlotsActivity` одновременно:

```text
создаёт frame
создаёт activity
регистрирует activity в screen
добавляет activity в hand_activities
удаляет activity из active_activities
удаляет frame из screen_frames
применяет fixture
считает layout
позиционирует frames
```

Для прототипа это допустимо, но при развитии проекта этот класс может стать источником трудноуловимых багов жизненного цикла.

Самый подозрительный участок — удаление prototype activity при `slot_count = 0`:

```python
activity = self.slot_activities.pop(frame_id, None)
if activity is None or activity is self.prototype_slot_activity:
    return
```

Здесь prototype activity удаляется из словаря `slot_activities`, но не завершается и не удаляется из screen. В результате состояние registry может стать несогласованным.

Перед дальнейшей интеграцией с `Controller` стоит разделить ответственность:

```text
SlotFrameManager      — создаёт/удаляет frames
SlotActivityManager   — создаёт/удаляет slot activities
PlayAreaSlotLayout    — только считает позиции
PlayAreaSlotsActivity — связывает эти части и реагирует на fixture/controller state
```

Даже если оставить всё в одном классе, полезно внутренне разделить методы именно по этим ролям.
