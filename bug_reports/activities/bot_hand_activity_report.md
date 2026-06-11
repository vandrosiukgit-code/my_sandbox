# Code Review Report: `bot_hand_activity(4).py`

## Контекст

Файл реализует `BotHandActivity` — долгоживущий визуальный Activity для отображения руки бота/игрока как веера закрытых или визуальных карт. Класс создает `Group`-объекты, синхронизирует их количество с `card_count`, применяет геометрию веера, управляет ресурсами карт и хранит данные для selection context.

Главная зона риска: класс одновременно отвечает за жизненный цикл generated-групп, ресурсный контракт, геометрию, трансформации поверхностей, layout invalidation, debug overlay и selection metadata. Это делает его важной базой для `PlayerHandActivity`, но также повышает риск скрытых багов при масштабировании.

---

## Краткое резюме

Код в целом выглядит рабочим и осмысленным, но в нем есть несколько архитектурных и технических рисков:

1. Возможная ошибка масштаба при расчете pivot после `pygame.transform.rotate`.
2. Прямой доступ к приватному полю `group._bot_hand_base_frames`.
3. Неочевидная связка `apply_card_transform()` и `frame.set_group_origin()`.
4. `calculate_fan_angles()` использует `count`, а не `count - 1`, из-за чего сектор веера может быть шире ожидаемого.
5. Слабая валидация `max_total_angle`, `radius`, `debug_fan_rect_color`, `card_resource_provider`.
6. Смешение нескольких ответственностей в одном классе.
7. Возможные проблемы при смене ресурсов и повторной синхронизации групп.
8. Debug overlay использует `group.rect`, что может быть экранной координатой, тогда как остальная геометрия локальная.

---

## 1. Потенциальная ошибка масштаба в `apply_card_transform()`

### Проблема

В `add_generated_group()` базовые кадры сохраняются так:

```python
group._bot_hand_base_frames = tuple(frame.copy() for frame in group.get_primary_layer_frames())
```

Затем в `apply_card_transform()` используется:

```python
base_surface = group._bot_hand_base_frames[0]
rotated_surface = pygame.transform.rotate(base_surface, -angle_degrees)

group.set_primary_layer_frames([rotated_surface], position=(0, 0))
group.set_scale_factor(self.scale_factor)
```

После этого `pivot_offset` считается от `base_surface.get_size()` и `rotated_surface.get_size()`, а затем дополнительно умножается на `offset_scale`:

```python
offset_scale = self.get_activity_local_scale()
group.set_local_rect((
    int(round(pivot_position[0] - pivot_offset[0] * offset_scale)),
    int(round(pivot_position[1] - pivot_offset[1] * offset_scale)),
    rotated_surface.get_width(),
    rotated_surface.get_height(),
))
```

Риск в том, что размер `local_rect` задается по неотмасштабированному `rotated_surface`, но offset пересчитывается через `offset_scale`. При этом сам `Group` получает `set_scale_factor(self.scale_factor)`.

Если `Group` сам применяет масштаб при отрисовке или расчете `rect`, то может возникнуть рассинхрон между:

- локальным прямоугольником;
- экранным прямоугольником;
- точкой pivot;
- hit area;
- debug overlay.

### Риск

Высокий, если в проекте используются разные масштабы frame/screen или если `scale_factor != 1.0`.

### Рекомендация

Явно выбрать один источник истины для масштаба:

- либо физически масштабировать surface перед поворотом;
- либо хранить surface в исходном размере, но весь layout считать в системе координат `Group`;
- либо полностью делегировать scale в `Group`, но тогда `local_rect` не должен частично компенсировать масштаб вручную.

Сейчас код выглядит как смешанная модель: surface не масштабируется, но offset масштабируется.

---

## 2. Метод `scale_surface()` не используется

### Проблема

В классе есть метод:

```python
def scale_surface(self, surface):
    ...
```

Но он нигде не вызывается.

Это особенно подозрительно на фоне проблемы с масштабированием в `apply_card_transform()`. Похоже, раньше планировалась модель, где поверхность масштабируется до поворота, но текущий код пошел другим путем.

### Риск

Средний. Сам по себе неиспользуемый метод не ломает код, но показывает незавершенную или изменившуюся архитектуру.

### Рекомендация

Либо удалить метод, либо использовать его явно:

```python
base_surface = self.scale_surface(group._bot_hand_base_frames[0])
rotated_surface = pygame.transform.rotate(base_surface, -angle_degrees)
group.set_scale_factor(None или 1.0)
```

Но перед этим нужно проверить, как `Group.set_scale_factor()` влияет на отрисовку и `rect`.

---

## 3. Прямое создание приватного поля в `Group`

### Проблема

Класс добавляет в объект `Group` новое приватное поле:

```python
group._bot_hand_base_frames = tuple(...)
```

Это хрупкая практика. `BotHandActivity` начинает расширять внутреннее состояние `Group` не через публичный интерфейс, а через ad-hoc атрибут.

### Риск

Средний/высокий.

Проблемы могут появиться, если:

- `Group` начнет использовать `__slots__`;
- изменится внутреннее устройство кадров;
- другой Activity тоже начнет добавлять свои приватные поля;
- потребуется сериализация/отладка/копирование групп;
- появится общий механизм reset/restore кадров.

### Рекомендация

Хранить базовые кадры внутри `BotHandActivity`:

```python
self.group_base_frames[group.id] = tuple(
    frame.copy() for frame in group.get_primary_layer_frames()
)
```

И затем:

```python
base_surface = self.group_base_frames[group.id][0]
```

Это лучше соответствует принципу владения: если `BotHandActivity` создал временные visual-only группы, он же хранит их служебное состояние.

---

## 4. Неочевидная связка `apply_card_transform()` и `set_group_origin()`

### Проблема

В `apply_fan_layout()` после трансформации вызывается:

```python
self.apply_card_transform(group, angle, (pivot_x, pivot_y))
self.frame.set_group_origin(group.id, group.local_rect.topleft)
```

Если `apply_card_transform()` уже изменяет `local_rect`, а `set_group_origin()` дополнительно синхронизирует origin внутри `Frame`, возникает риск двойного управления координатами.

### Риск

Высокий для интерактивности и hit-test.

Типичные симптомы:

- карта визуально находится в одном месте, а кликается в другом;
- debug rect показывает не то место;
- порядок отрисовки или координаты группы отстают на один layout;
- после resize frame карты временно прыгают;
- selection context возвращается правильно, но выбранная зона не совпадает с картой.

### Рекомендация

Нужно явно зафиксировать контракт:

- `group.local_rect` — источник истины?
- `frame.set_group_origin()` — источник истины?
- или `place_group_local()` должен быть единственным способом перемещения?

Если `set_group_origin()` обязателен для Frame, стоит обернуть перемещение в один метод:

```python
def move_group_to_local_rect(self, group, local_rect):
    group.set_local_rect(local_rect)
    self.frame.set_group_origin(group.id, group.local_rect.topleft)
```

Так будет хотя бы видно, что это единая операция.

---

## 5. `calculate_fan_angles()` может занимать слишком широкий сектор

### Проблема

Текущий код:

```python
reference_step = self.max_total_angle / self.reference_card_count
if count <= self.reference_card_count:
    occupied_angle = reference_step * count
    return occupied_angle, reference_step

compressed_step = self.max_total_angle / count
return self.max_total_angle, compressed_step
```

А позиция карты считается так:

```python
return -occupied_angle / 2 + angle_step / 2 + index * angle_step
```

Фактически карты размещаются по центрам слотов. Для `count = 9` и `max_total_angle = 160`:

```text
reference_step = 17.77
occupied_angle = 160
centers: -71.11 ... +71.11
```

Крайние центры не доходят до ±80, потому что сектор делится на 9 слотов, а карты стоят в центрах слотов.

Это может быть задумано, но название `max_total_angle` становится неоднозначным: это не угол между крайними картами, а ширина виртуального сектора слотов.

### Риск

Средний.

Визуально веер может казаться уже, чем ожидает разработчик по параметру `max_total_angle`.

### Альтернатива

Если `max_total_angle` должен означать угол между крайними картами, расчет должен быть через `count - 1`:

```python
angle_step = self.max_total_angle / (count - 1)
local_angle = -self.max_total_angle / 2 + index * angle_step
```

Если текущая модель намеренная, стоит переименовать параметр или уточнить docstring:

```text
max_total_angle is the occupied slot sector, not the exact angle between edge cards.
```

---

## 6. Нет нормализации `max_total_angle`

### Проблема

В `__init__`:

```python
self.max_total_angle = float(max_total_angle)
```

Значение может быть отрицательным или чрезмерным.

### Риск

Средний.

При отрицательном угле веер инвертируется. При слишком большом угле карты могут оказаться в неожиданном положении.

### Рекомендация

Добавить нормализацию:

```python
@staticmethod
def normalize_non_negative_float(value, name, maximum=None):
    value = float(value)
    if value < 0:
        raise ValueError(f"{name} must be non-negative: {value!r}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}: {value!r}")
    return value
```

И использовать:

```python
self.max_total_angle = self.normalize_non_negative_float(
    max_total_angle,
    "max_total_angle",
    maximum=360.0,
)
```

---

## 7. `radius` может быть отрицательным

### Проблема

В `__init__`:

```python
self.radius = float(radius)
```

В `apply_fixture()`:

```python
self.radius = float(fixture.get("radius", self.radius))
```

Отрицательный радиус технически допустим, но, скорее всего, не является нормальным публичным параметром.

### Риск

Средний.

Отрицательный radius зеркально переносит карты относительно центра веера. Это может быть трудно отлаживать, особенно если значение пришло из fixture.

### Рекомендация

Если отрицательный радиус не нужен как осознанный режим, валидировать:

```python
self.radius = self.normalize_non_negative_float(radius, "radius")
```

---

## 8. `apply_fixture()` вызывает `set_card_count()` даже если изменились только геометрические параметры

### Проблема

В конце `apply_fixture()`:

```python
self.set_card_count(fixture.get("card_count", self.card_count))
```

`set_card_count()` всегда делает:

```python
self.sync_visual_groups()
self.apply_fan_layout()
```

Даже если `card_count` не изменился, а изменились только `radius`, `center_offset` или `scale_factor`.

### Риск

Низкий/средний.

Для dev fixture это терпимо, но при частом применении fixture может быть лишняя работа.

### Рекомендация

Разделить:

```python
if "card_count" in fixture:
    self.set_card_count(fixture["card_count"])
else:
    self.apply_fan_layout()
```

Или сделать `set_card_count()` идемпотентным.

---

## 9. `configure_card_resources()` может очищать все группы при смене provider

### Проблема

```python
resources_changed = (
    provider is not self.card_resource_provider
    or (layer_name is not None and layer_name != self.card_layer_name)
)
```

Сравнение provider идет по identity. Если вызывающий код каждый раз передает новый lambda/function-wrapper, группы будут постоянно пересоздаваться.

### Риск

Средний.

Может проявиться как:

- лишние пересоздания групп;
- потеря hover/selection state;
- мерцание карт;
- сброс group ids/metadata;
- лишняя нагрузка на pygame surfaces.

### Рекомендация

Если provider должен быть стабильным объектом — явно задокументировать это.

Если нет — лучше сравнивать итоговые resource keys.

---

## 10. `sync_visual_groups()` очищает все группы при первом несовпадении resource key

### Проблема

```python
for index, group in enumerate(tuple(self.generated_groups)):
    expected_key = self.get_card_resource_key(index)
    if self.group_resource_keys.get(group.id) != expected_key:
        self.clear_generated_groups()
        break
```

Если ресурс изменился у одной карты, пересоздаются все группы.

### Риск

Средний.

Для закрытых карт бота это нормально. Для player hand или видимых карт это может быть дорого и может сбивать состояние.

### Рекомендация

Если это базовый класс для интерактивной руки, лучше предусмотреть точечную замену группы по индексу:

```python
self.replace_generated_group(index, expected_key)
```

Или оставить текущее поведение, но явно пометить:

```text
Intentional: generated visual groups are cheap and stateless.
```

---

## 11. Возможная проблема уникальности `group_id`

### Проблема

```python
group_id = f"{self.group_id_prefix}.{index}"
```

Если одна и та же рука пересоздается без очистки старых групп, или два Activity используют одинаковый `group_id_prefix`, возможен конфликт id.

### Риск

Средний.

Особенно если Activity могут пересоздаваться при смене экрана, fixture или режима.

### Рекомендация

Гарантировать уникальный `group_id_prefix` на уровне владельца или добавить защиту перед `place_group_local()`.

---

## 12. `get_card_id()` зависит от `resource_key`

### Проблема

```python
return f"{self.group_id_prefix}.card.{index}:{resource_key}"
```

Если resource key меняется, card id меняется. Для визуальной руки бота это нормально. Но для интерактивной player hand это может быть проблемой, если selection state должен переживать смену ресурса/лица карты.

### Риск

Средний для наследников.

### Рекомендация

Для базового класса нормально, но в docstring стоит уточнить:

```text
card_id is stable only while group_id_prefix, index and resource_key remain stable.
```

Для реальных игровых карт лучше передавать настоящий card_id из модели, а не генерировать его из resource key.

---

## 13. `get_card_selection_context()` смешивает визуальный slot и игровую сущность

### Проблема

Метод возвращает:

```python
{
    "group_id": group.id,
    "hand_index": hand_index,
    "card_id": ...,
    "resource_key": ...,
    "frame_id": self.frame.id,
}
```

Это удобно, но `BotHandActivity` по верхнему docstring не должен знать жизненный цикл реальных карт. При этом `card_id` может восприниматься контроллером как игровая сущность.

### Риск

Средний.

В будущем можно случайно начать принимать визуальный `card_id` за настоящий id карты в модели.

### Рекомендация

Переименовать поле, если это именно визуальный id:

```python
"visual_card_id": ...
```

А настоящий id карты передавать отдельно через provider/adapter для player hand.

---

## 14. `draw()` не рисует группы, но docstring говорит иначе

### Проблема

```python
def draw(self, screen):
    """Отрисовать generated visual-only Group, которыми владеет Activity."""
    self.draw_debug_overlay(screen)
```

Фактически метод не рисует группы. Он рисует только debug overlay. Вероятно, группы рисует `GameScreen`.

### Риск

Низкий, но создает путаницу.

### Рекомендация

Изменить docstring:

```python
def draw(self, screen):
    """Draw optional debug overlays; generated groups are drawn by GameScreen."""
    self.draw_debug_overlay(screen)
```

---

## 15. Debug overlay может использовать не ту систему координат

### Проблема

```python
bounds = group.rect.copy() if bounds is None else bounds.union(group.rect)
pygame.draw.rect(screen, self.debug_fan_rect_color, bounds, 2)
```

Если `group.rect` — экранный rect, все нормально. Если он локальный или обновляется не синхронно с `local_rect`, overlay будет неверным.

### Риск

Низкий/средний.

### Рекомендация

Уточнить контракт `group.rect`. Если overlay рисуется на `screen`, rect должен быть экранным.

Возможно, стоит назвать метод точнее:

```python
calculate_fan_screen_rect()
```

---

## 16. `debug_fan_rect_color` почти не валидируется

### Проблема

```python
self.debug_fan_rect_color = tuple(debug_fan_rect_color)
```

Если передать некорректную длину или значения, ошибка возникнет позже в `pygame.draw.rect`.

### Риск

Низкий.

### Рекомендация

Добавить нормализацию цвета.

---

## 17. `calculate_rotated_pivot_offset()` зависит от знака угла

### Проблема

Surface поворачивается так:

```python
rotated_surface = pygame.transform.rotate(base_surface, -angle_degrees)
```

А pivot offset считается так:

```python
rotated_vector = bottom_center_from_source_center.rotate(angle_degrees)
```

Знак угла противоположный. Возможно, это правильно из-за различия экранной системы координат и математической системы `pygame.Vector2.rotate()`. Но это место неочевидное.

### Риск

Средний.

Если кто-то поменяет знак в одном месте, pivot сломается.

### Рекомендация

Добавить комментарий прямо в метод:

```python
# pygame.transform.rotate uses counter-clockwise visual rotation;
# layout angle uses screen-space clockwise convention, so signs differ.
```

И желательно покрыть тестом на 0°, 90°, -90°.

---

## 18. Layout signature может быть дорогим при большом количестве карт

### Проблема

```python
tuple(self.get_card_resource_key(index) for index in range(self.card_count))
```

Каждый `update()` вызывает `get_layout_signature()`. Если `card_resource_provider` дорогой или имеет побочные эффекты, это проблема.

### Риск

Низкий для обычной руки карт, но архитектурно важно.

### Рекомендация

Требовать, чтобы provider был чистой дешевой функцией, или кэшировать resource keys при `sync_visual_groups()`.

---

## 19. `get_activity_screen_scale()` возвращает `scale_factor`, а не экранный масштаб

### Проблема

```python
def get_activity_screen_scale(self):
    if self.scale_factor is None:
        return self.get_frame_screen_scale()
    return self.scale_factor
```

Название метода может вводить в заблуждение. Если `scale_factor=0.8`, метод возвращает не screen scale, а activity visual scale.

Потом:

```python
return self.get_activity_screen_scale() / self.get_frame_screen_scale()
```

Это может быть правильно, но названия усложняют понимание.

### Рекомендация

Переименовать или уточнить:

```python
get_activity_visual_scale()
get_activity_local_scale()
```

---

## 20. Базовый класс уже содержит интерактивный selection context

### Проблема

`BotHandActivity` по смыслу — визуальная рука бота. Но в нем есть:

- `group_hand_indices`;
- `group_card_ids`;
- `get_card_selection_context()`.

Это полезно для `PlayerHandActivity`, но делает базовый класс менее чистым.

### Риск

Средний.

Класс начинает быть не только “визуальной рукой бота”, но и базой для интерактивной руки игрока.

### Рекомендация

Варианты:

1. Оставить как есть, но переименовать класс в более общий:
   - `VisualHandActivity`
   - `FanHandActivity`
   - `GeneratedHandActivity`

2. Разделить:
   - `GeneratedHandActivity` — создание групп и resources;
   - `FanHandLayoutMixin` — геометрия веера;
   - `SelectableHandMixin` — selection context;
   - `BotHandActivity` — конкретная визуальная рука бота.

---

## Приоритеты исправления

### Высокий приоритет

1. Проверить контракт масштаба в `apply_card_transform()`.
2. Проверить связку `group.local_rect` + `frame.set_group_origin()`.
3. Убрать хранение `_bot_hand_base_frames` внутри `Group`.
4. Уточнить или исправить семантику `max_total_angle`.

### Средний приоритет

5. Добавить нормализацию `max_total_angle` и `radius`.
6. Уточнить стабильность `card_id`.
7. Уточнить контракт `card_resource_provider`.
8. Исправить docstring `draw()`.
9. Добавить комментарий про знак угла в `calculate_rotated_pivot_offset()`.

### Низкий приоритет

10. Валидировать `debug_fan_rect_color`.
11. Переименовать методы scale для большей ясности.
12. Оптимизировать `get_layout_signature()` только если появятся реальные performance-проблемы.

---

## Рекомендуемый минимальный refactor

Минимальный безопасный рефактор без изменения поведения:

```python
class BotHandActivity(Activity):
    def __init__(...):
        ...
        self.group_base_frames = {}
```

В `add_generated_group()`:

```python
self.group_base_frames[group.id] = tuple(
    frame.copy() for frame in group.get_primary_layer_frames()
)
```

В `apply_card_transform()`:

```python
base_surface = self.group_base_frames[group.id][0]
```

В `clear_generated_groups()`:

```python
self.group_base_frames = {}
```

Плюс исправить docstring `draw()`:

```python
def draw(self, screen):
    """Draw optional debug overlays; generated groups are drawn by GameScreen."""
    self.draw_debug_overlay(screen)
```

И добавить нормализацию:

```python
self.max_total_angle = self.normalize_non_negative_float(
    max_total_angle,
    "max_total_angle",
    maximum=360.0,
)
self.radius = self.normalize_non_negative_float(radius, "radius")
```

---

## Рекомендуемый следующий шаг

Перед крупным рефакторингом нужно проверить фактический контракт `Group` и `Frame`:

1. Что делает `Group.set_scale_factor()`?
2. В какой системе координат живет `group.local_rect`?
3. Что именно делает `frame.set_group_origin()`?
4. Использует ли hit-test `group.rect`, `group.local_rect` или данные `Frame`?
5. Кто реально рисует generated groups: `GameScreen`, `Frame` или сам `Activity`?

Без ответов на эти вопросы опасно радикально менять `apply_card_transform()`, потому что главные риски находятся именно на стыке layout, scale, frame-origin и hit-test.
