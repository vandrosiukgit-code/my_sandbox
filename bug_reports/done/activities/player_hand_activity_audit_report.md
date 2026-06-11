# Отчёт о проблемах в `player_hand_activity.py`

**Предложенное имя файла:** `player_hand_activity_audit_report.md`

## Контекст

Файл содержит `PlayerHandActivity` — наследника `BotHandActivity`, который переопределяет геометрию веера для интерактивной руки игрока.

По смыслу класс делает следующее:

```text
BotHandActivity
-> создаёт visual-only card groups
-> умеет поворачивать и размещать карты

PlayerHandActivity
-> использует тот же механизм групп
-> меняет алгоритм раскладки
-> делает веер более горизонтальным и удобным для hover/click
-> задаёт draw order слева направо
```

Также файл реэкспортирует:

```python
CardsSlotActivityDecorator
VisibleCardsHandDecorator
PlayerHandActivity
```

Класс выглядит как специализированная версия `BotHandActivity` для нижней руки игрока. Основные риски связаны с наследованием, повторным использованием проблемного `apply_card_transform()` из `BotHandActivity`, невалидированными параметрами fixture и неявной связью с `CardSelectionActivity`.

---

## 1. Наследуются все проблемы `BotHandActivity.apply_card_transform()`

### Проблема

`PlayerHandActivity.apply_fan_layout()` использует:

```python
self.apply_card_transform(
    group,
    self.orientation_degrees + local_angle,
    pivot_position,
)
```

Этот метод приходит из `BotHandActivity`.

### Почему это опасно

Если в `BotHandActivity.apply_card_transform()` есть проблемы с:

- масштабированием;
- pivot;
- знаком угла;
- `group.layers[0]`;
- `local_rect` и фактическим размером rotated surface;

то `PlayerHandActivity` автоматически наследует все эти визуальные баги.

### Рекомендация

Сначала исправить transform pipeline в `BotHandActivity`, а уже потом настраивать player-specific geometry.

Иначе можно долго подкручивать `max_card_angle`, `fan_width_ratio`, `center_offset`, но реальная причина смещения карт будет находиться в базовом transform-коде.

---

## 2. `max_total_angle` в базовом классе задаётся только при `__init__`

### Проблема

В конструкторе:

```python
super().__init__(*args, max_total_angle=max_card_angle * 2, **kwargs)
self.max_card_angle = float(max_card_angle)
```

Но в `apply_fixture()` меняется только:

```python
self.max_card_angle = float(fixture.get("max_card_angle", self.max_card_angle))
```

Поле `self.max_total_angle`, унаследованное от `BotHandActivity`, после этого не обновляется.

### Почему это может быть не критично

`PlayerHandActivity.apply_fan_layout()` использует `self.max_card_angle`, а не `self.max_total_angle`.

### Почему это всё равно риск

Если какой-то внешний код или унаследованный метод из `BotHandActivity` использует `max_total_angle`, он будет видеть старое значение.

Например:

```python
calculate_fan_angles()
```

у базового класса опирается на `self.max_total_angle`.

### Рекомендация

Синхронизировать поля:

```python
self.max_card_angle = float(fixture.get("max_card_angle", self.max_card_angle))
self.max_total_angle = self.max_card_angle * 2
```

Или вообще не хранить `max_total_angle` для `PlayerHandActivity`, если базовая логика веера больше не используется.

---

## 3. `apply_fixture()` не валидирует параметры

### Проблема

Метод принимает значения напрямую:

```python
self.max_card_angle = float(fixture.get("max_card_angle", self.max_card_angle))
self.edge_padding_ratio = float(fixture.get("edge_padding_ratio", self.edge_padding_ratio))
self.fan_width_ratio = float(fixture.get("fan_width_ratio", self.fan_width_ratio))
```

### Почему это опасно

Можно передать:

```python
max_card_angle = -999
edge_padding_ratio = -10
fan_width_ratio = 100
fan_width_ratio = "abc"
```

Часть значений сломает layout, часть создаст странную геометрию.

### Рекомендация

Добавить нормализацию:

```python
self.max_card_angle = max(0.0, min(90.0, float(value)))
self.edge_padding_ratio = max(0.0, min(0.45, float(value)))
self.fan_width_ratio = max(0.0, min(1.0, float(value)))
```

Если нужны значения больше 1 для debug — можно разрешить, но тогда это должно быть осознанно.

---

## 4. `fan_width_ratio` может вывести карты за границы frame

### Проблема

В `calculate_fan_geometry()`:

```python
half_span = available_half_span * self.fan_width_ratio
```

Если `fan_width_ratio > 1`, карты могут выйти за рассчитанные left/right bounds.

### Почему это опасно

Параметр называется ratio, поэтому ожидается диапазон `0.0 ... 1.0`.

Если fixture случайно задаст `1.5`, геометрия перестанет соответствовать смыслу edge padding.

### Рекомендация

Ограничивать:

```python
self.fan_width_ratio = max(0.0, min(1.0, float(value)))
```

Или переименовать параметр, если значения больше 1 допустимы как intentional overscan.

---

## 5. `edge_padding_ratio` может сделать available span равным нулю

### Проблема

Padding считается так:

```python
padding = self.calculate_edge_padding(frame_rect)
left_bound = frame_rect.left + padding
right_bound = frame_rect.right - padding
```

Если `edge_padding_ratio >= 0.5`, то `left_bound >= right_bound`.

Дальше:

```python
available_half_span = max(
    0,
    min(center_x - left_bound, right_bound - center_x),
)
```

получится `0`.

### Почему это опасно

Все карты окажутся по одному `center_x`.

### Рекомендация

Ограничивать `edge_padding_ratio`:

```python
0.0 <= edge_padding_ratio < 0.5
```

Например:

```python
self.edge_padding_ratio = max(0.0, min(0.45, float(value)))
```

---

## 6. `max_card_angle = 0` делает дугу плоской и радиус `None`

### Поведение

```python
max_angle = abs(float(self.max_card_angle))
angle_radians = math.radians(max_angle)

radius = None
if half_span > 0 and angle_radians > 0:
    radius = half_span / math.sin(angle_radians)
```

Если угол равен нулю, `radius = None`, а `calculate_arc_y()` возвращает `0`.

### Почему это нормально

Это даёт полностью горизонтальную раскладку без дуги.

### Потенциальная проблема

Если `max_card_angle` случайно стал `0`, диагностики не будет.

### Рекомендация

Если плоская рука допустима — оставить.

Если нет — валидировать минимальный угол, например:

```python
max_card_angle >= 1.0
```

---

## 7. Радиус может стать очень большим при маленьком `max_card_angle`

### Проблема

Радиус считается так:

```python
radius = half_span / math.sin(angle_radians)
```

Для очень маленького угла `sin(angle)` близок к нулю, поэтому radius станет очень большим.

### Почему это может быть проблемой

`calculate_arc_y()` делает:

```python
radius * (1 - math.cos(math.radians(angle_degrees)))
```

Математически для малых углов результат может быть нормальным, но численно это менее устойчиво и сложнее для отладки.

### Рекомендация

Для маленьких углов использовать приближение или считать дугу как простую параболу.

Например:

```python
arc_y = arc_depth * (slot ** 2)
```

Для UI-веера это часто проще и предсказуемее, чем настоящая окружность.

---

## 8. `calculate_slot_position()` использует `reference_card_count`, а не фактическую ширину карты

### Проблема

Позиция слота нормализуется так:

```python
reference_count = max(count, self.reference_card_count)
max_slot_offset = max(1.0, (reference_count - 1) / 2)
slot_offset = index - (count - 1) / 2

return max(-1.0, min(1.0, slot_offset / max_slot_offset))
```

### Почему это может быть хорошо

Маленькие руки не растягиваются на всю ширину веера. Например 2-3 карты остаются компактно около центра.

### Почему это может быть проблемой

Плотность зависит от `reference_card_count`, а не от реального размера карты, масштаба и overlap.

При разных `scale_factor` карты могут:

- слишком сильно перекрываться;
- слишком далеко расходиться;
- создавать неудобные hit-зоны.

### Рекомендация

Для интерактивной руки лучше рассчитывать spacing от фактической ширины карты и доступного пространства.

Например:

```text
desired_step = card_width * visible_ratio
max_step = available_width / (count - 1)
step = min(desired_step, max_step)
```

А угол можно выводить из нормализованной позиции.

---

## 9. `calculate_slot_position()` для больших рук зажимает крайние карты в `[-1, 1]`

### Поведение

```python
return max(-1.0, min(1.0, slot_offset / max_slot_offset))
```

Так как `reference_count = max(count, self.reference_card_count)`, для больших рук крайние карты обычно попадают в `-1` и `1`.

### Почему это нормально

Это ограничивает веер.

### Потенциальная проблема

При очень большом количестве карт карты будут всё сильнее уплотняться, но hit detection может стать неудобным.

### Рекомендация

Для больших рук стоит предусмотреть:

- horizontal scrolling;
- compact mode;
- pagination;
- selection zoom;
- раскрытие карты по hover поверх всей руки.

---

## 10. `calculate_arc_y()` всегда добавляет положительный Y

### Проблема

```python
return radius * (1 - math.cos(math.radians(angle_degrees)))
```

Результат всегда `>= 0`.

В `apply_fan_layout()`:

```python
geometry["center_y"] + self.calculate_arc_y(local_angle, geometry)
```

То есть края всегда уходят вниз относительно центра.

### Почему это может быть правильно

Для нижней руки игрока это может выглядеть как дуга, где центральные карты выше, а края ниже.

### Почему это может быть проблемой

Если `orientation_degrees`, положение frame или дизайн руки изменятся, направление дуги останется зашитым.

### Рекомендация

Добавить параметр:

```python
arc_direction = 1
```

или:

```python
arc_y_sign
```

Чтобы можно было управлять направлением дуги.

---

## 11. Геометрия завязана на нижнюю руку, но класс называется общо

### Проблема

Docstring говорит:

```text
The bottom player's hand is interactive
```

и `draw()` говорит:

```python
"""Draw bottom-hand cards from left to right so right cards sit on top."""
```

Но класс называется просто:

```python
PlayerHandActivity
```

### Почему это опасно

Если позже появятся разные player hands: bottom, top, left, right, этот класс может быть ошибочно использован не для нижней руки.

### Рекомендация

Либо переименовать:

```python
BottomPlayerHandActivity
```

Либо добавить параметры ориентации/режима, чтобы класс действительно был универсальным для player hands.

---

## 12. `draw()` может дублировать draw из `Frame`

### Проблема

Как и в `BotHandActivity`, `draw()` сам рисует generated groups:

```python
for group in self.iter_groups_in_draw_order():
    group.draw(screen)
```

Если эти группы также добавлены во frame и frame их рисует, возможна двойная отрисовка.

### Почему это опасно

Симптомы:

- карты выглядят темнее;
- непонятный z-order;
- draw order из `PlayerHandActivity` конфликтует с draw order frame;
- hover/debug может не совпадать с визуалом.

### Рекомендация

Решить, кто владеет отрисовкой generated groups:

```text
или Activity рисует группы сама
или Frame рисует зарегистрированные группы
```

Если draw order важен именно для player hand, лучше не давать frame рисовать эти же группы вторично.

---

## 13. Draw order сортируется только по `local_rect.centerx`

### Проблема

```python
return tuple(sorted(self.generated_groups, key=self.get_group_draw_x))
```

и:

```python
return group.local_rect.centerx
```

### Почему это подходит

Для нижней горизонтальной руки это логично: правая карта рисуется позже и оказывается сверху.

### Почему это может быть проблемой

Если рука будет не горизонтальной или появятся другие ориентации, сортировка по `x` станет неправильной.

### Рекомендация

Если класс только для bottom hand — оставить и явно указать.

Если класс должен быть универсальным — draw order должен зависеть от ориентации руки или z-index.

---

## 14. `get_group_draw_x()` использует `local_rect`, а не screen rect

### Проблема

```python
return group.local_rect.centerx
```

### Почему это может быть нормально

Все карты находятся в одном frame, поэтому local x достаточно.

### Потенциальная проблема

Если группы окажутся в разных parent frame или frame будет трансформирован, local order может не совпасть с screen order.

### Рекомендация

Для текущей архитектуры оставить.

Если появятся вложенные трансформации, использовать screen rect или явный slot index.

---

## 15. `apply_fan_layout()` не сохраняет slot/index metadata на группе

### Проблема

Layout знает `index`, но не сохраняет его:

```python
for index, group in enumerate(self.generated_groups):
    ...
```

### Почему это может быть проблемой

Для интерактивной руки выбор карты часто должен возвращать индекс карты в руке.

Если `CardSelectionActivity` потом выбирает `Group`, нужно где-то понять, какая это карта:

```text
group -> hand index
```

### Рекомендация

При layout или создании группы сохранять metadata:

```python
group._hand_index = index
```

Лучше не через приватное поле, а через явный mapping:

```python
self.group_to_hand_index[group.id] = index
```

---

## 16. Импорты `CardsSlotActivityDecorator` и `VisibleCardsHandDecorator` выглядят лишними для логики файла

### Проблема

Файл импортирует:

```python
from activities.cards_slot_activity import CardsSlotActivityDecorator
from activities.visible_cards_hand_activity import VisibleCardsHandDecorator
```

Но внутри `PlayerHandActivity` они не используются. Они только реэкспортируются в `__all__`.

### Почему это может быть нормально

Возможно, файл используется как public facade:

```python
from activities.player_hand_activity import PlayerHandActivity, VisibleCardsHandDecorator
```

### Почему это может быть проблемой

Это создаёт лишние зависимости и риск циклических импортов.

Например:

```text
visible_cards_hand_activity imports something
cards_slot_activity imports VisibleCardsHandDecorator
player_hand_activity imports both
```

### Рекомендация

Если реэкспорт нужен — оставить, но явно понимать, что файл является facade.

Если нет — убрать импорты и оставить только:

```python
__all__ = ["PlayerHandActivity"]
```

---

## 17. Потенциальный циклический импорт

### Проблема

`player_hand_activity.py` импортирует:

```python
CardsSlotActivityDecorator
VisibleCardsHandDecorator
```

При этом `cards_slot_activity.py` сам импортирует:

```python
VisibleCardsHandDecorator
```

А другие файлы могут импортировать `PlayerHandActivity` как общий модуль.

### Почему это опасно

По мере роста проекта такой facade может легко создать цикл импортов.

### Рекомендация

Держать `player_hand_activity.py` узким: только `PlayerHandActivity`.

Для public re-export лучше сделать отдельный модуль, например:

```python
activities/hand_activities.py
```

---

## 18. Нет type hints

### Проблема

Методы не аннотированы:

```python
def apply_fixture(self, fixture):
def calculate_fan_geometry(self):
def calculate_slot_position(self, index, count):
```

### Почему это важно

Этот класс работает с геометрией, где типы координат и rect особенно важны.

### Рекомендация

Добавить минимальные hints:

```python
def calculate_slot_position(self, index: int, count: int) -> float:
    ...

def calculate_arc_y(angle_degrees: float, geometry: dict) -> float:
    ...
```

Для geometry лучше использовать dataclass вместо dict.

---

## 19. `calculate_fan_geometry()` возвращает dict вместо структурированного объекта

### Проблема

Метод возвращает:

```python
return {
    "center_x": center_x,
    "center_y": center_y,
    "half_span": half_span,
    "max_angle": max_angle,
    "radius": radius,
}
```

### Почему это может быть нормально

Для маленького метода dict удобен.

### Почему это может быть проблемой

Ошибки в ключах проявятся только runtime-ошибкой:

```python
geometry["center_y"]
geometry["radius"]
```

### Рекомендация

Сделать dataclass:

```python
@dataclass(frozen=True)
class PlayerHandFanGeometry:
    center_x: int
    center_y: int
    half_span: float
    max_angle: float
    radius: float | None
```

---

## 20. `calculate_fan_geometry()` не учитывает размеры самой карты

### Проблема

Доступная ширина считается от центра до границ frame:

```python
available_half_span = max(
    0,
    min(center_x - left_bound, right_bound - center_x),
)
```

Но размер карты не вычитается.

### Почему это опасно

Pivot может быть внутри bounds, но сама карта после поворота и масштаба может выходить за frame.

### Рекомендация

При расчёте доступного span учитывать половину ширины карты или bounding box rotated card.

Простой вариант:

```text
available_half_span = available_half_span - card_width / 2
```

Более точный вариант — учитывать rotated/scaled bounds.

---

## 21. `center_offset` из базового класса может вывести веер из безопасной области

### Проблема

`calculate_fan_geometry()` использует:

```python
center_x, center_y = self.get_fan_center(frame_rect)
```

А `get_fan_center()` берётся из `BotHandActivity` и учитывает `center_offset`.

Если `center_offset.x` сильно сместит центр, `available_half_span` может стать `0`.

### Почему это опасно

Все карты могут схлопнуться в одну точку или веер станет сильно асимметричным.

### Рекомендация

Либо валидировать `center_offset`, либо после вычисления `center_x` clamp-ить его внутри допустимой области.

---

## 22. `orientation_degrees` из базового класса может конфликтовать с player-specific геометрией

### Проблема

Поворот карты задаётся так:

```python
self.orientation_degrees + local_angle
```

Для нижней руки предполагается некая базовая ориентация.

### Почему это опасно

Если fixture изменит `orientation_degrees`, визуальная форма может перестать соответствовать hit-zone ожиданиям `CardSelectionActivity`.

### Рекомендация

Для `PlayerHandActivity` стоит явно определить допустимую ориентацию.

Если нижняя рука всегда должна иметь один orientation, можно не прокидывать этот параметр из fixture или валидировать его.

---

# Приоритет исправлений

## Высокий приоритет

1. Сначала исправить transform pipeline в `BotHandActivity`, потому что `PlayerHandActivity` использует `apply_card_transform()`.
2. Синхронизировать `max_total_angle` с `max_card_angle` или удалить зависимость от `max_total_angle`.
3. Добавить валидацию `max_card_angle`, `edge_padding_ratio`, `fan_width_ratio`.
4. Убедиться, что generated groups не рисуются дважды: через frame и через `PlayerHandActivity.draw()`.
5. Добавить явный mapping `group -> hand_index` для будущего выбора карты.

## Средний приоритет

6. Учитывать размер карты при расчёте доступной ширины веера.
7. Документировать, что класс рассчитан именно на bottom player hand, или переименовать его.
8. Проверить, не конфликтует ли `orientation_degrees` с player-specific layout.
9. Решить, нужны ли re-export imports в этом файле.
10. Заменить geometry dict на dataclass.

## Низкий приоритет

11. Добавить type hints.
12. Добавить параметр направления дуги.
13. Пересмотреть spacing для больших рук.
14. Проверить устойчивость при маленьком `max_card_angle`.
15. Упростить или задокументировать `reference_card_count` как density-параметр.

---

# Главный вывод

`PlayerHandActivity` — это правильное направление для интерактивной руки: отделить геометрию игрока от декоративной геометрии бота.

Но сейчас класс всё ещё сильно зависит от базового `BotHandActivity`, особенно от метода:

```python
self.apply_card_transform(...)
```

Поэтому любые ошибки с pivot, scale и rotated surface в базовом классе будут проявляться и здесь.

Самая важная архитектурная задача — отделить три слоя:

```text
1. generated groups lifecycle
2. card transform pipeline: scale -> rotate -> pivot -> local rect
3. player-specific layout: slot position -> arc y -> angle
```

`PlayerHandActivity` должен отвечать в основном за третий слой. Если первые два слоя останутся неустойчивыми, настройка player hand будет постоянно превращаться в борьбу с побочными эффектами базового класса.
