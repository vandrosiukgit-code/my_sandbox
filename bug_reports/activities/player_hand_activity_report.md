# Code Review Report: `player_hand_activity.py`

## Краткое резюме

Файл `player_hand_activity.py` реализует отдельную геометрию руки игрока, отличную от декоративных рук ботов. Основная идея выглядит правильной: нижняя рука игрока интерактивная, поэтому веер карт должен быть более предсказуемым по горизонтали и удобным для hit detection.

Главные риски находятся не в синтаксисе, а в согласованности между визуальной трансформацией карты, `local_rect`, origin группы и областью клика. Самое подозрительное место — вызов `self.frame.set_group_origin(group.id, group.local_rect.topleft)` сразу после `self.apply_card_transform(...)`.

## Приоритеты проверки

| Приоритет | Проблема | Риск |
|---|---|---|
| P1 | `apply_card_transform()` + `frame.set_group_origin()` | Возможное несовпадение визуальной позиции и кликабельной зоны |
| P1 | Сжатие веера через `reference_card_count` | Карты игрока могут занимать слишком мало ширины |
| P2 | Учет ширины только первой карты | Крайние карты могут выходить за границы при разных размерах |
| P2 | Сортировка отрисовки по `centerx` | Возможные скачки порядка перекрытия карт |
| P3 | Пустой `draw()` с misleading docstring | Путаница при сопровождении |
| P3 | Импорт и экспорт неиспользуемых декораторов | Лишняя связность модуля |

---

## 1. Возможный рассинхрон визуальной позиции и зоны клика

### Код

```python
self.apply_card_transform(
    group,
    self.orientation_degrees + local_angle,
    pivot_position,
)

self.frame.set_group_origin(group.id, group.local_rect.topleft)
```

### Почему это опасно

`apply_card_transform()` вероятно меняет позицию, угол или pivot группы. После этого `set_group_origin()` устанавливает origin группы через `group.local_rect.topleft`.

Если `local_rect` не синхронизирован с итоговой трансформированной позицией, может появиться типичный баг:

- карта визуально находится в одном месте;
- кликабельная зона находится в другом;
- порядок отрисовки рассчитывается по старым или промежуточным координатам;
- frame хранит origin, который не совпадает с фактической позицией группы.

### Что проверить

1. Что именно делает `apply_card_transform()`.
2. Меняет ли он `group.local_rect`.
3. Нужен ли после него `frame.set_group_origin()`.
4. Какая система координат используется в `CardSelectionActivity`.

### Рекомендация

Если `apply_card_transform()` уже обновляет позицию группы, лучше убрать повторную установку origin или заменить ее на явный метод, который синхронизирует frame с итоговой позицией группы.

Например:

```python
self.apply_card_transform(
    group,
    self.orientation_degrees + local_angle,
    pivot_position,
)

# Только если это действительно нужно после transform:
self.frame.sync_group_origin(group.id)
```

Если такого метода нет, стоит явно документировать, зачем `set_group_origin()` вызывается именно после transform.

---

## 2. `calculate_slot_position()` может слишком сильно сжимать веер

### Код

```python
reference_count = max(count, self.reference_card_count)
max_slot_offset = max(1.0, (reference_count - 1) / 2)
slot_offset = index - (count - 1) / 2

return max(-1.0, min(1.0, slot_offset / max_slot_offset))
```

### Проблема

Если `self.reference_card_count` больше текущего количества карт, текущие карты не используют всю доступную ширину веера.

Например, если в руке 3 карты, но `reference_card_count = 10`, слоты будут примерно такими:

```text
-0.22, 0.0, 0.22
```

А не такими:

```text
-1.0, 0.0, 1.0
```

### Когда это нормально

Это может быть осознанным решением, если нужна стабильная геометрия: карты не должны резко разъезжаться, когда их становится меньше.

### Когда это плохо

Для руки игрока это может ухудшить интерактивность:

- карты будут скучены в центре;
- кликабельные зоны будут плотнее;
- свободное место по бокам останется неиспользованным;
- визуально рука будет выглядеть менее выразительно.

### Рекомендация

Явно разделить два режима:

```python
def calculate_slot_position(self, index, count):
    if count <= 1:
        return 0.0

    if self.use_stable_reference_fan:
        reference_count = max(count, self.reference_card_count)
    else:
        reference_count = count

    max_slot_offset = max(1.0, (reference_count - 1) / 2)
    slot_offset = index - (count - 1) / 2
    return max(-1.0, min(1.0, slot_offset / max_slot_offset))
```

Или, если стабильность не нужна, упростить:

```python
def calculate_slot_position(self, index, count):
    if count <= 1:
        return 0.0
    return -1.0 + 2.0 * index / (count - 1)
```

---

## 3. Ширина карты берется только у первой группы

### Код

```python
def get_card_local_half_width(self):
    if not self.generated_groups:
        return 0.0
    return max(0.0, self.generated_groups[0].local_rect.width / 2)
```

### Проблема

Если все карты всегда одинакового размера, это безопасно. Но если в будущем появятся разные размеры карт, эффекты, scale, selected-state или визуальные модификаторы, первая карта может оказаться не самой широкой.

Тогда расчет `available_half_span` может быть неверным, и крайние карты смогут выйти за границы `frame.content_rect`.

### Рекомендация

Использовать максимальную ширину среди всех групп:

```python
def get_card_local_half_width(self):
    return max(
        (group.local_rect.width / 2 for group in self.generated_groups),
        default=0.0,
    )
```

---

## 4. `center_x` лучше зажимать с учетом половины ширины карты

### Код

```python
center_x = max(left_bound, min(right_bound, center_x))
available_half_span = max(
    0,
    min(center_x - left_bound, right_bound - center_x) - card_half_width,
)
```

### Проблема

Сейчас `center_x` может быть зажат прямо в `left_bound` или `right_bound`. После этого `available_half_span` станет нулевым или почти нулевым.

В результате веер может схлопнуться, даже если во frame есть место для карты.

### Рекомендация

Зажимать центр веера с учетом половины ширины карты:

```python
center_x = max(
    left_bound + card_half_width,
    min(right_bound - card_half_width, center_x),
)
```

Это делает геометрию устойчивее: центр веера не окажется там, где сама карта уже не помещается.

---

## 5. Радиус может стать слишком большим при маленьком угле

### Код

```python
radius = None
if half_span > 0 and angle_radians > 0:
    radius = half_span / math.sin(angle_radians)
```

### Проблема

При очень маленьком `max_card_angle`, например `1°`, `math.sin(angle_radians)` будет очень малым, а радиус станет очень большим.

Это не обязательно вызовет ошибку, но значения станут плохо читаемыми и могут приводить к неочевидному поведению при экстремальных настройках.

### Рекомендация

Ввести минимальный рабочий угол:

```python
min_angle_radians = math.radians(0.5)

radius = None
if half_span > 0 and angle_radians >= min_angle_radians:
    radius = half_span / math.sin(angle_radians)
```

Или явно считать маленький угол плоской раскладкой:

```python
if angle_radians < math.radians(0.5):
    radius = None
```

---

## 6. Порядок отрисовки завязан только на `centerx`

### Код

```python
def iter_groups_in_draw_order(self):
    return tuple(sorted(self.generated_groups, key=self.get_group_draw_x))

@staticmethod
def get_group_draw_x(group):
    return group.local_rect.centerx
```

### Проблема

Для веера карт порядок перекрытия обычно важнее, чем просто X-координата. Если карты поворачиваются, анимируются или временно смещаются, `centerx` может измениться так, что порядок отрисовки начнет прыгать.

### Рекомендация

Если у карты или группы есть индекс в руке, лучше сортировать по нему. Если такого индекса нет, можно сохранять порядок при генерации:

```python
def iter_groups_in_draw_order(self):
    return tuple(self.generated_groups)
```

Или использовать стабильный ключ:

```python
def iter_groups_in_draw_order(self):
    return tuple(
        sorted(
            enumerate(self.generated_groups),
            key=lambda item: item[0],
        )
    )
```

Идеальный вариант зависит от того, как именно должны перекрываться карты: слева направо, справа налево, центральная поверх остальных и т.д.

---

## 7. `reference_card_count` используется неявно

### Код

```python
reference_count = max(count, self.reference_card_count)
```

### Проблема

`reference_card_count` не задается в этом классе. Видимо, оно приходит из `BotHandActivity`. Это нормально, если базовый класс гарантирует наличие поля.

Но для читаемости и устойчивости класса зависимость лучше сделать явной.

### Рекомендация

Минимальный безопасный вариант:

```python
reference_count = max(count, getattr(self, "reference_card_count", count))
```

Более правильный архитектурный вариант — явно документировать в `PlayerHandActivity`, что он зависит от `BotHandActivity.reference_card_count`.

---

## 8. Пустой `draw()` с неточным docstring

### Код

```python
def draw(self, screen):
    """Draw debug overlays for this activity; groups are drawn by GameScreen."""
    _ = screen
```

### Проблема

Docstring говорит про debug overlays, но метод ничего не рисует. Это может путать при сопровождении.

### Рекомендация

Если debug overlays не нужны:

```python
def draw(self, screen):
    """Groups are drawn by GameScreen."""
    pass
```

Если debug overlays планируются, лучше добавить TODO:

```python
def draw(self, screen):
    """Groups are drawn by GameScreen. Debug overlays are not implemented yet."""
    pass
```

---

## 9. Импорт и экспорт декораторов создают лишнюю связность

### Код

```python
from activities.cards_slot_activity import CardsSlotActivityDecorator
from activities.visible_cards_hand_activity import VisibleCardsHandDecorator

__all__ = [
    "CardsSlotActivityDecorator",
    "PlayerHandActivity",
    "VisibleCardsHandDecorator",
]
```

### Проблема

Декораторы не используются внутри файла, но экспортируются из него. Это может быть сделано намеренно как публичный API, но по коду это неочевидно.

### Рекомендация

Если это compatibility export, добавить комментарий:

```python
# Re-export decorators for compatibility with existing imports.
```

Если совместимость не нужна, убрать импорты и удалить декораторы из `__all__`.

---

## 10. Смешение ответственностей

Сейчас класс отвечает сразу за несколько вещей:

- нормализацию параметров;
- применение fixture;
- расчет геометрии веера;
- применение layout к группам;
- порядок отрисовки;
- частичный публичный API через `__all__`.

Файл пока не слишком большой, но направление роста опасное. Если логика руки игрока будет усложняться, лучше отделить расчет геометрии от activity.

### Возможная структура

```text
PlayerHandActivity
├── отвечает за жизненный цикл activity
├── применяет layout к generated_groups
└── использует PlayerFanGeometryCalculator

PlayerFanGeometryCalculator
├── считает bounds
├── считает half_span
├── считает radius
└── считает slot positions
```

---

## Рекомендуемый минимальный набор правок

### 1. Сделать расчет ширины карты безопаснее

```python
def get_card_local_half_width(self):
    return max(
        (group.local_rect.width / 2 for group in self.generated_groups),
        default=0.0,
    )
```

### 2. Зажимать `center_x` с учетом ширины карты

```python
center_x = max(
    left_bound + card_half_width,
    min(right_bound - card_half_width, center_x),
)
```

### 3. Проверить необходимость `set_group_origin()` после transform

```python
self.apply_card_transform(
    group,
    self.orientation_degrees + local_angle,
    pivot_position,
)

# Проверить: действительно ли этот вызов нужен после transform.
self.frame.set_group_origin(group.id, group.local_rect.topleft)
```

### 4. Уточнить поведение `calculate_slot_position()`

Нужно принять архитектурное решение:

- либо веер стабильный относительно `reference_card_count`;
- либо текущие карты всегда используют всю доступную ширину.

Для интерактивной руки игрока второй вариант часто удобнее.

---

## Итог

Код выглядит рабочим и достаточно аккуратным, но в нем есть несколько мест, которые могут привести к визуально неприятным и трудноуловимым багам.

Главный риск — не математика веера, а синхронизация координат после трансформации карт. Если сейчас есть проблемы с кликами, hover, selection или порядком перекрытия, начинать диагностику нужно с `apply_card_transform()` и `frame.set_group_origin()`.

