# Code Review Report: `cards_slot_activity(3).py`

## 1. Краткое резюме

`CardsSlotActivityDecorator` — декоратор поверх `VisibleCardsHandDecorator`, который нормализует визуальные группы карт так, чтобы их общий локальный bounds начинался от `(0, 0)` внутри frame слота. Класс также хранит прямоугольники занятого содержимого и умеет отдавать bounds в локальных и screen-координатах.

В целом файл небольшой и понятный, но в нем есть несколько архитектурных и практических рисков:

- нормализация позиции вызывается слишком часто;
- есть риск накопления ошибок/дребезга позиции при повторных пересчетах;
- смешаны обязанности декоратора, layout-нормализации и debug-отрисовки;
- screen/local/scaled rect могут расходиться по смыслу;
- `draw_debug_overlay()` использует жестко заданный цвет;
- класс сильно зависит от внутреннего поведения `hand_activity.frame` и `Group`.

Самая подозрительная зона — `move_generated_groups_to_slot_origin()`, потому что она физически двигает группы после layout родительской активности и вызывается из нескольких мест.

---

## 2. Основные проблемы

### 2.1. `move_generated_groups_to_slot_origin()` вызывается на каждом `update()`

```python
    def update(self, dt):
        super().update(dt)
        self.move_generated_groups_to_slot_origin()
```

Это может быть избыточно. Если карты и frame не менялись, повторное перемещение групп каждый кадр не нужно.

Риски:

- лишняя работа каждый frame;
- сложнее отлаживать позиционирование;
- возможны микросмещения, если `move_group_local()` не является строго идемпотентной операцией;
- parent-layout может пытаться выставить одну позицию, а декоратор сразу же ее нормализует.

Рекомендация: вызывать нормализацию только при изменении входных данных:

- после `set_cards()`;
- после `apply_fixture()`;
- после изменения layout signature;
- после изменения размера frame;
- после пересоздания generated groups.

Можно завести `_last_slot_signature`.

---

### 2.2. Возможный конфликт с layout логикой `hand_activity`

Класс сначала вызывает:

```python
super().update(dt)
```

А затем физически двигает группы:

```python
self.move_generated_groups_to_slot_origin()
```

Если `VisibleCardsHandDecorator` или вложенный `hand_activity` тоже управляют позицией карт, получается двухступенчатая схема:

1. базовая активность выставляет layout;
2. slot-декоратор сдвигает результат к origin.

Это допустимо, но опасно, если кто-то выше ожидает, что позиции групп соответствуют исходному layout.

Риск особенно заметен, если:

- hover/selection используют `local_rect`;
- другой декоратор ожидает исходную позицию;
- анимация использует старую позицию как rest-state;
- debug overlay сравнивает разные coordinate spaces.

Рекомендация: явно оформить это как отдельный layout stage, например:

```text
base hand layout -> slot normalization -> interaction/debug
```

И не смешивать нормализацию с обычным `update()` без проверки изменений.

---

### 2.3. `slot_content_local_rect` и `slot_content_scaled_local_rect` могут быть семантически неочевидны

```python
self.slot_content_local_rect = pygame.Rect(0, 0, bounds.width, bounds.height)
scaled_bounds = self.calculate_generated_groups_scaled_local_bounds()
self.slot_content_scaled_local_rect = scaled_bounds.copy()
```

После перемещения групп `slot_content_local_rect` принудительно начинается с `(0, 0)`, а `slot_content_scaled_local_rect` берется из фактических scaled bounds.

Проблема: scaled bounds могут иметь не нулевые `x/y`, если `get_scaled_local_rect()` учитывает scale относительно центра или другой pivot.

В результате:

- `get_slot_content_rect()` возвращает scaled rect;
- `get_slot_content_unscaled_local_rect()` возвращает rect от `(0, 0)`;
- эти два rect могут отличаться не только размером, но и origin.

Это может путать вызывающий код.

Рекомендация: решить, что публичный slot content rect означает:

- либо всегда bounds с реальным `x/y`;
- либо всегда нормализованный rect от `(0, 0)`;
- либо разделить API явно: `get_slot_bounds_actual_*` и `get_slot_size_*`.

---

### 2.4. `get_slot_content_rect()` возвращает scaled rect, хотя название нейтральное

```python
    def get_slot_content_rect(self):
        """Return visible occupied card bounds in slot frame-local coordinates."""
        return self.get_slot_content_scaled_local_rect()
```

Название `get_slot_content_rect()` не говорит, что rect уже scaled.

Это может привести к ошибкам, если вызывающий код ожидает обычные локальные координаты без учета scale.

Рекомендация: либо переименовать метод, либо изменить docstring:

```python
    def get_slot_content_rect(self):
        """Return scaled occupied card bounds in slot frame-local coordinates."""
```

Еще лучше — оставить старый метод как compatibility alias, но в новом коде использовать явные методы:

- `get_slot_content_unscaled_local_rect()`;
- `get_slot_content_scaled_local_rect()`;
- `get_slot_content_screen_rect()`.

---

### 2.5. Жестко заданный debug color

```python
pygame.draw.rect(screen, (255, 232, 64), rect, 2)
```

В отличие от `BotHandActivity`, где debug color передается через параметр, здесь цвет зашит прямо в метод.

Минусы:

- сложнее конфигурировать debug overlay;
- нарушается единообразие с другими Activity;
- при нескольких overlay цвета могут конфликтовать.

Рекомендация: вынести в поле:

```python
self.debug_slot_rect_color = (255, 232, 64)
```

И желательно добавить флаг:

```python
self.debug_slot_rect = False
```

Сейчас overlay рисуется всегда, если rect не пустой.

---

### 2.6. Debug overlay рисуется всегда

```python
    def draw_debug_overlay(self, screen):
        rect = self.get_slot_content_screen_rect()
        if rect.width > 0 and rect.height > 0:
            pygame.draw.rect(screen, (255, 232, 64), rect, 2)
```

Метод называется `draw_debug_overlay`, но внутри нет флага включения/выключения.

Если внешний код вызывает `draw_debug_overlay()`, прямоугольник будет рисоваться всегда.

Рекомендация: добавить явный флаг:

```python
if not self.debug_slot_rect:
    return
```

---

### 2.7. `validate_slot_hand_activity()` проверяет только `move_group_local()`

```python
frame = getattr(hand_activity, "frame", None)
if frame is None or not callable(getattr(frame, "move_group_local", None)):
    raise TypeError(...)
```

Для работы класса также нужны:

- `hand_activity.frame`;
- `iter_generated_groups()` через базовый декоратор;
- корректные `group.local_rect`;
- `group.rect`;
- возможно `group.get_scaled_local_rect()`.

Проверяется только один метод frame.

Это не обязательно баг, но контракт неполный.

Рекомендация: либо расширить проверку, либо описать минимальный контракт в docstring.

---

### 2.8. Возможная проблема с порядком вызовов в `__init__()`

```python
super().__init__(...)
self.validate_slot_hand_activity(hand_activity)
```

Валидация происходит после инициализации родительского декоратора.

Если `hand_activity` некорректный, ошибка может возникнуть внутри `VisibleCardsHandDecorator` раньше, чем сработает понятное сообщение `CardsSlotActivityDecorator requires...`.

Рекомендация: валидировать до `super().__init__()`:

```python
self.validate_slot_hand_activity(hand_activity)
super().__init__(...)
```

---

### 2.9. `move_generated_groups_to_slot_origin()` зависит от текущего bounds и сразу меняет эти же группы

```python
bounds = self.calculate_generated_groups_local_bounds()

for group in self.iter_generated_groups():
    rect = group.local_rect
    self.hand_activity.frame.move_group_local(
        group,
        (rect.x - bounds.x, rect.y - bounds.y),
    )
```

Логика выглядит правильно: найти общий bounds и сдвинуть все группы так, чтобы bounds.x/y стали нулем.

Но есть риск, если `move_group_local()` работает не как set-position, а как relative move. По названию `move_group_local` не очевидно, является ли второй аргумент абсолютной позицией или дельтой.

Код предполагает, что это абсолютная новая позиция.

Рекомендация: если метод действительно принимает абсолютную позицию, лучше использовать более явный API, например:

```python
set_group_local_position(group, position)
```

Если такой возможности нет — добавить комментарий:

```python
# move_group_local() expects absolute frame-local top-left position.
```

---

### 2.10. `calculate_generated_groups_screen_bounds()` использует `group.rect`

```python
rect = group.rect
```

Если `group.rect` — screen-space rect, все хорошо. Но если в проекте есть различие между local rect, scaled local rect и screen rect, это место становится зависимым от внутренней реализации `Group`.

Рекомендация: если есть явный метод преобразования local -> screen, лучше использовать его. Например:

```python
group.local_rect_to_screen_rect(group.local_rect)
```

Иначе стоит явно зафиксировать контракт в комментарии:

```python
# group.rect is expected to be screen-space bounds.
```

---

## 3. Приоритеты исправления

### P1 — проверить в первую очередь

1. Убедиться, что `move_group_local(group, position)` принимает абсолютную позицию, а не дельту.
2. Проверить, не ломает ли `move_generated_groups_to_slot_origin()` rest-state hover/selection.
3. Убрать постоянную нормализацию из каждого `update()` или добавить signature-check.

### P2 — улучшить API и читаемость

1. Уточнить смысл `get_slot_content_rect()`.
2. Развести unscaled/scaled/screen bounds по понятным публичным методам.
3. Перенести `validate_slot_hand_activity()` до `super().__init__()`.

### P3 — косметика и поддерживаемость

1. Добавить debug flag.
2. Вынести debug color в параметр/поле.
3. Расширить docstring контракта класса.

---

## 4. Рекомендуемый минимальный патч

### 4.1. Добавить layout signature

```python
    def get_slot_layout_signature(self):
        return tuple(
            (group.id, group.local_rect.x, group.local_rect.y, group.local_rect.width, group.local_rect.height)
            for group in self.iter_generated_groups()
        )
```

И в `update()`:

```python
    def update(self, dt):
        super().update(dt)
        signature = self.get_slot_layout_signature()
        if signature != getattr(self, "_last_slot_layout_signature", None):
            self.move_generated_groups_to_slot_origin()
            self._last_slot_layout_signature = self.get_slot_layout_signature()
```

Важно: после нормализации signature изменится, поэтому `_last_slot_layout_signature` лучше сохранять после перемещения.

---

### 4.2. Добавить debug-флаг

```python
    def __init__(self, hand_activity, cards=None, resource_manager=None, max_cards=2, debug_slot_rect=False):
        self.validate_slot_hand_activity(hand_activity)
        super().__init__(
            hand_activity,
            cards=cards,
            resource_manager=resource_manager,
            max_cards=max_cards,
        )
        self.debug_slot_rect = bool(debug_slot_rect)
        self.debug_slot_rect_color = (255, 232, 64)
```

```python
    def draw_debug_overlay(self, screen):
        if not self.debug_slot_rect:
            return
        rect = self.get_slot_content_screen_rect()
        if rect.width > 0 and rect.height > 0:
            pygame.draw.rect(screen, self.debug_slot_rect_color, rect, 2)
```

---

### 4.3. Уточнить публичный API rect-методов

```python
    def get_slot_content_rect(self):
        """Compatibility alias: return scaled occupied card bounds in frame-local coordinates."""
        return self.get_slot_content_scaled_local_rect()
```

---

## 5. Архитектурная рекомендация

Сейчас `CardsSlotActivityDecorator` делает сразу три вещи:

1. декорирует visible hand activity;
2. нормализует layout к origin слота;
3. рисует debug bounds.

Более чистая схема:

```text
VisibleCardsHandDecorator
    отвечает за создание/обновление видимых карт

CardsSlotLayoutNormalizer
    отвечает только за перенос bounds к origin

CardsSlotDebugOverlay
    отвечает только за debug-отрисовку
```

Но для текущего размера файла полный рефакторинг не обязателен. Достаточно ограничить `move_generated_groups_to_slot_origin()` так, чтобы он не выполнялся без необходимости каждый кадр.

---

## 6. Итог

Код в целом компактный и выполняет понятную задачу, но его главный риск — не сами вычисления bounds, а то, что декоратор постоянно физически перепозиционирует группы после базовой активности.

Главная рекомендация: сделать нормализацию идемпотентной и вызывать ее только при изменении layout/cards/frame, а не каждый `update()`.

