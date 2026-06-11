# Обобщённый архитектурный отчёт по проблемам Activity-кода

**Предложенное имя файла:** `activity_architecture_audit_report.md`

## Контекст

Этот отчёт обобщает проблемы, найденные в наборе Activity-файлов, связанных с визуальными руками игроков/ботов, выбором карт, слотами игровой области и ходом игрока.

Обработанные файлы:

- `bot_hand_activity.py`
- `card_selection_activity.py`
- `cards_slot_activity.py`
- `play_area_slots_activity.py`
- `player_turn_activity.py`
- `visible_cards_hand_activity.py`
- `player_hand_activity.py`

Отчёт не фокусируется на отдельных строках кода. Его цель — показать повторяющиеся архитектурные проблемы и подходы к написанию кода, которые со временем могут привести к сложным багам.

Главный общий диагноз:

```text
Код уже движется в сторону Activity-архитектуры, но Activity пока слишком много знают о внутренностях других Activity, Frame, Group и Screen.
```

---

# 1. Критические проблемы подхода

## 1.1. Смешение жизненного цикла, layout и владения объектами

Во многих классах одна и та же сущность одновременно:

- создаёт visual groups;
- добавляет их во frame;
- двигает их;
- рисует их;
- удаляет их;
- запускает другие activity;
- завершает другие activity;
- меняет registry экрана;
- применяет fixture;
- рассчитывает layout.

Например, `PlayAreaSlotsActivity` одновременно:

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

Это делает класс слишком ответственным за всё сразу.

### Почему это критично

Когда один класс управляет слишком многими слоями, становится трудно понять:

- кто владеет объектом;
- кто имеет право его удалить;
- кто отвечает за перерисовку;
- кто отвечает за layout;
- кто должен знать о завершении activity;
- кто должен синхронизировать registry.

В результате может появиться состояние, где:

```text
объект визуально ещё существует,
но activity уже удалена из одного registry,
но осталась в другом,
а другой класс всё ещё держит ссылку.
```

### Рекомендуемый подход

Разделить ответственность:

```text
Activity lifecycle     — запуск/остановка режима
Layout                 — расчёт позиций
Frame/Group manager    — создание/удаление визуальных объектов
Renderer               — порядок отрисовки
Controller             — игровые решения
```

Даже если всё остаётся в одном классе, методы должны быть разделены по этим ролям:

```python
sync_slot_frames()
sync_slot_activities()
apply_slot_fixtures()
calculate_layout()
place_slot_frames()
cleanup_removed_slots()
```

---

## 1.2. Неявное владение вложенными Activity

В коде часто встречается pattern:

```python
self.hand_activity.start()
self.hand_activity.finish()
self.play_area_slots_activity.start()
self.play_area_slots_activity.finish()
```

Проблема в том, что неясно, вложенная activity является:

```text
собственностью текущей activity
```

или:

```text
долгоживущим сервисом экрана, которым текущая activity только пользуется
```

### Почему это критично

Если `PlayerTurnActivity.finish()` завершает `PlayAreaSlotsActivity`, то завершение одного хода игрока может случайно уничтожить всю систему слотов стола.

Если `CardSelectionActivity.finish()` завершает `hand_activity`, то завершение режима выбора может удалить визуальную руку, хотя рука должна остаться на экране.

### Рекомендуемый подход

Добавить явный флаг владения:

```python
def __init__(self, hand_activity, owns_hand_activity=True):
    self.hand_activity = hand_activity
    self.owns_hand_activity = owns_hand_activity
```

И использовать его:

```python
def finish(self):
    if self.owns_hand_activity:
        self.hand_activity.finish()
    super().finish()
```

Или принять глобальное правило:

```text
Activity, которая создаёт child activity, обязана её завершить.
Activity, которая получила activity извне, не завершает её без явного флага.
```

---

## 1.3. Визуальные сущности используются как игровые сущности

Сейчас выбор карты идёт через visual `Group`:

```python
selected_group = self.find_card_at(...)
self.start_player_turn(selected_group)
```

Но `Group` — это визуальный объект, а не игровая карта.

### Почему это критично

Visual group может:

- быть пересоздана;
- поменять id;
- измениться при layout;
- быть proxy для карты;
- не содержать игрового смысла;
- принадлежать временной анимации.

Если в игровую логику передаётся `Group`, Controller начинает зависеть от визуального слоя.

### Рекомендуемый подход

Разделить visual selection и game selection:

```text
screen_pos
-> visual group
-> hand_index / card_id
-> GameController command
-> visual reaction
```

Внутри hand activity или selection activity должен быть mapping:

```python
group_id -> hand_index
group_id -> card_id
```

В `GameController` должен уходить не `Group`, а стабильная игровая сущность:

```text
card_id
hand_index
turn command
```

---

## 1.4. Прямое изменение внутренних структур других объектов

В коде встречаются прямые изменения чужих внутренних полей:

```python
self.frame.group_origins[group.id] = ...
self.screen.screen_frames.pop(...)
self.play_area_frame.child_frames.pop(...)
self.screen.active_activities.remove(...)
self.hand_activity.card_resource_provider = ...
self.hand_activity.card_layer_name = ...
self.hand_activity.card_count = ...
```

### Почему это критично

Такой код обходит возможную внутреннюю логику объекта:

- dirty flags;
- layout cache;
- z-order;
- input/collision cache;
- deferred removal;
- debug registry;
- animation cleanup;
- parent/child synchronization.

То есть внешний класс меняет данные напрямую, а объект-владелец может даже не узнать, что его состояние изменилось.

### Рекомендуемый подход

Заменить прямую мутацию публичными методами:

```python
frame.set_group_origin(group_id, position)
screen.remove_frame(frame_id)
screen.remove_activity(activity)
hand_activity.configure_card_resources(...)
group.sync_origin_with_parent_frame()
```

Принцип:

```text
Не менять внутренние поля чужого объекта напрямую.
Просить объект выполнить действие через его публичный метод.
```

---

# 2. Очень серьёзные проблемы

## 2.1. Смешение координатных систем

В проекте одновременно используются:

- `local_rect`;
- `rect`;
- `screen_pos`;
- `content_rect`;
- `scaled_local_rect`;
- `frame.to_local(...)`;
- `group.local_rect_to_screen_rect(...)`.

Но не всегда явно понятно, в какой системе координат находится конкретный rect.

### Примеры проблемного подхода

В одном месте bounds может считаться через scaled rect, а позиция группы потом изменяться через обычный local rect:

```python
bounds = self.calculate_generated_groups_bounds()
rect = group.local_rect
group.set_local_position(rect.x - bounds.x, rect.y - bounds.y)
```

Если `bounds` находится в scaled-local coordinates, а `group.local_rect` — в unscaled-local coordinates, результат будет математически неверным.

В другом месте rect может быть получен либо от frame, либо от activity:

```python
activity.calculate_fan_rect()
screen.get_screen_frame(frame_id).rect
```

Но корректность зависит от того, что оба rect находятся в одной системе координат.

### Почему это серьёзно

Ошибки координатных систем трудно ловить:

- всё выглядит “почти правильно”;
- баг проявляется только при scale;
- баг проявляется только при resize;
- баг проявляется только при другой ориентации frame;
- debug rect может не совпадать с визуальным объектом.

### Рекомендуемый подход

Ввести жёсткое соглашение об именах:

```text
local_rect          — координаты внутри parent frame
screen_rect         — координаты на экране
scaled_local_rect   — local rect с учётом scale
content_local_rect  — content area внутри frame
```

И переименовать методы:

```python
calculate_fan_screen_rect()
calculate_fan_local_rect()
get_scaled_local_rect()
local_rect_to_screen_rect()
screen_rect_to_local_rect()
```

Главное правило:

```text
Метод должен по имени говорить, в какой системе координат он работает.
```

---

## 2.2. Неустойчивый transform pipeline карт

В базовой hand activity карта проходит сложный путь:

```text
base surface
-> rotate surface
-> положить surface в layer
-> применить group scale
-> отдельно посчитать pivot
-> задать local_rect по rotated surface
```

Здесь смешиваются:

- scale surface;
- scale group;
- frame local scale;
- rotation;
- pivot;
- local rect;
- фактический rendered size.

### Почему это серьёзно

Если масштабирование происходит в одном месте, а pivot считается в другом, карта может визуально не попадать в рассчитанную точку.

Особенно опасно, что `PlayerHandActivity` наследует этот transform pipeline. Значит, все ошибки базового transform-кода переходят и в интерактивную руку игрока.

### Рекомендуемый подход

Упростить pipeline:

```text
base surface
-> scale surface
-> rotate scaled surface
-> calculate pivot on actual rotated surface
-> set local rect
-> draw without additional group scale
```

То есть:

```text
один источник масштаба
одна система координат
pivot считается по реально используемой surface
```

Это сделает layout гораздо проще для отладки.

---

## 2.3. Возможная двойная отрисовка

Некоторые generated groups:

1. добавляются во frame;
2. затем вручную рисуются из Activity.

Например:

```python
self.frame.add_group_id(group.id)
```

и затем:

```python
for group in self.generated_groups:
    group.draw(screen)
```

### Почему это серьёзно

Если frame тоже рисует эти группы, они будут отрисованы дважды.

Симптомы:

- карты выглядят темнее;
- порядок слоёв становится непонятным;
- правая карта может рисоваться поверх не там, где ожидается;
- debug hit rect может не совпадать с визуалом;
- hover может казаться сломанным.

### Рекомендуемый подход

Выбрать один источник отрисовки:

```text
Вариант A:
Activity владеет generated groups и сама их рисует.
Тогда frame не должен рисовать эти groups.

Вариант B:
Frame владеет отрисовкой всех зарегистрированных groups.
Тогда Activity не должна вызывать group.draw(screen).
```

Смешивать оба подхода нельзя.

---

## 2.4. Layout пересчитывается не всегда, когда меняются условия

Во многих классах layout пересчитывается только при:

- `start()`;
- `apply_fixture()`;
- `set_card_count()`;
- ручном вызове layout-метода.

Но layout может устареть из-за:

- изменения размера frame;
- изменения scale;
- изменения количества карт;
- изменения ресурсов;
- resize окна;
- изменения play area;
- изменения положения рук игроков;
- изменения slot content.

### Почему это серьёзно

Визуальное состояние может стать stale:

```text
данные изменились,
а layout остался старым.
```

Это особенно опасно в UI, потому что ошибка может быть не crash, а “почему-то всё съехало”.

### Рекомендуемый подход

Ввести dirty-флаг:

```python
self.layout_dirty = True
```

Или layout signature:

```python
signature = (
    frame.content_rect,
    card_count,
    scale_factor,
    resource_keys,
    orientation,
    slot_content_size,
)
```

И пересчитывать layout только при изменении signature.

---

# 3. Средние проблемы архитектуры

## 3.1. Декораторы слишком глубоко изменяют wrapped activity

Например, visible-card decorator напрямую меняет wrapped hand activity:

```python
self.hand_activity.card_resource_provider = self.get_card_resource_key
self.hand_activity.card_layer_name = "card"
self.hand_activity.card_count = len(self.card_resource_keys)
```

### Почему это проблема

Такой декоратор уже не просто добавляет поведение. Он перепрошивает внутреннее состояние другой activity.

Если wrapped activity используется где-то ещё, её поведение неожиданно изменится.

### Рекомендуемый подход

Если декоратор получает эксклюзивное владение activity — явно написать это в контракте.

Лучше заменить прямую мутацию на метод:

```python
hand_activity.configure_card_resources(
    provider=self.get_card_resource_key,
    layer_name="card",
    card_count=len(self.card_resource_keys),
)
```

---

## 3.2. Слабые контракты между Activity

Код часто предполагает, что у объекта есть нужные поля или методы:

```python
self.hand_activity.generated_groups
self.hand_activity.clear_generated_groups()
self.play_area_slots_activity.apply_fixture(fixture)
self.prototype_slot_activity.get_slot_content_rect()
```

Но эти интерфейсы явно не описаны.

### Почему это проблема

Когда классов становится больше, трудно понять:

- какой объект можно передавать;
- какие методы обязательны;
- какие методы optional;
- какие поля считаются публичными;
- какие поля являются внутренними.

### Рекомендуемый подход

Добавить Protocol или хотя бы type hints:

```python
class HandActivityLike(Protocol):
    generated_groups: Sequence[Group]

    def start(self) -> None: ...
    def update(self, dt: float) -> None: ...
    def apply_fixture(self, fixture: dict) -> None: ...
    def clear_generated_groups(self) -> None: ...
```

Даже если типы будут неполными, они уже помогут зафиксировать контракты.

---

## 3.3. `fixture` используется как универсальный канал всего

Через fixture передаются:

- геометрия;
- `card_count`;
- resource keys;
- debug-режимы;
- `slot_count`;
- spacing;
- origin;
- center;
- step;
- cards from manifest.

### Почему это проблема

Fixture превращается в “мешок параметров”.

Из-за этого:

- легко передать несовместимые поля;
- один и тот же ключ может иметь разный смысл на разных уровнях;
- нет строгой схемы;
- частичный fixture может случайно сбросить дефолты;
- сложно понять, какие поля реально поддерживаются.

### Рекомендуемый подход

Постепенно перейти к typed config/view model:

```python
HandLayoutConfig
VisibleCardsConfig
PlayAreaSlotsConfig
SlotActivityConfig
```

Или хотя бы разделить fixture на секции:

```python
{
    "layout": {...},
    "cards": {...},
    "debug": {...},
    "slot_activity": {...}
}
```

---

## 3.4. Нет явного разделения dev/debug и runtime-кода

Некоторые механизмы явно временные, например:

```text
cards_from_manifest
temporary GUI debug source
Controller must provide real hand cards
```

### Почему это проблема

Debug-механизм со временем может случайно стать частью runtime-контракта.

### Рекомендуемый подход

Разделить источники данных:

```text
Runtime path:
Controller -> card view models -> VisibleCardsHandDecorator

Debug path:
ManifestFixtureProvider -> card resource keys -> VisibleCardsHandDecorator
```

То есть debug должен подготавливать те же данные, что и runtime, но не быть встроенным в основную activity-логику.

---

## 3.5. Жёстко зашитые id и предположения о layout

В layout-коде встречаются конкретные id:

```python
left_player_hand
left_player_frame
right_player_hand
right_player_frame
```

А `PlayerHandActivity` по смыслу является нижней рукой игрока, хотя называется обобщённо.

### Почему это проблема

Код становится привязан к конкретному экрану и конкретной схеме имён.

Если id изменится, layout может silently fallback-нуться на дефолтное поведение.

### Рекомендуемый подход

Передавать такие зависимости через constructor/config:

```python
left_player_activity_id
left_player_frame_id
right_player_activity_id
right_player_frame_id
hand_orientation
```

Или переименовать специализированные классы:

```python
BottomPlayerHandActivity
```

если они не должны быть универсальными.

---

# 4. Локальные проблемы качества кода

## 4.1. Недостаточная валидация входных параметров

Многие значения приводятся через `float()` или `int()` без проверки диапазона:

```text
scale_factor
radius
max_card_angle
edge_padding_ratio
fan_width_ratio
spacing
origin
slot_offsets
max_cards
```

### Почему это проблема

Некорректный fixture может не вызвать понятную ошибку, а просто сломать layout.

Например:

```text
scale_factor = 0
fan_width_ratio = 100
edge_padding_ratio = 0.9
max_card_angle = -999
```

### Рекомендуемый подход

Валидировать параметры сразу при чтении:

```text
scale_factor > 0
0 <= edge_padding_ratio < 0.5
0 <= fan_width_ratio <= 1
max_card_angle >= 0
slot_count >= 1 или явно поддержать 0
```

---

## 4.2. Состояние хранится прямо на объектах `Group`

В selection activity состояние hover/rest может записываться прямо в group:

```python
group._card_selection_base_position
group._card_selection_base_scale
```

### Почему это проблема

Это создаёт скрытую связь между Activity и Group.

Возможные последствия:

- другая activity может использовать такие же поля;
- состояние переживёт activity;
- трудно понять, кто изменил group;
- при повторном использовании group старое состояние может быть неактуальным.

### Рекомендуемый подход

Хранить такое состояние внутри activity:

```python
self.rest_states[group.id] = {
    "position": tuple(group.local_rect.topleft),
    "scale": group.scale_factor or 1.0,
}
```

---

## 4.3. Жёсткая работа с `group.layers[0]`

Некоторые методы предполагают, что нужный слой всегда первый:

```python
group.layers[0].frames = [...]
group.layers[0].position = (0, 0)
```

Но одновременно существует параметр:

```python
card_layer_name
```

### Почему это проблема

Если структура group изменится, код начнёт менять не тот слой.

### Рекомендуемый подход

Получать слой по имени:

```python
card_layer = group.get_layer(self.card_layer_name)
```

Если такого метода нет, стоит добавить его в `Group`.

---

## 4.4. Неиспользуемые или вводящие в заблуждение параметры

В коде есть элементы, которые читаются или объявляются, но фактически не используются:

```text
columns
get_center_out_offset()
scale_surface()
```

### Почему это проблема

Такой код сбивает с толку:

- непонятно, какой алгоритм актуальный;
- кажется, что параметр влияет на поведение, хотя он ничего не делает;
- растёт технический долг.

### Рекомендуемый подход

Для каждого такого элемента принять решение:

```text
использовать
удалить
или явно пометить как TODO
```

---

# 5. Незначительные, но накопительные проблемы

## 5.1. Мало type hints

Большинство методов не аннотированы.

### Почему это важно

Проект уже содержит много неявных интерфейсов:

```text
Frame-like
Group-like
Activity-like
Screen-like
ResourceManager-like
Fixture dict
```

Без type hints сложно безопасно развивать систему.

### Рекомендуемый подход

Добавлять type hints постепенно, начиная с чистых helper-методов:

```python
def normalize_pair(value) -> tuple[int, int]:
    ...

def calculate_slot_position(self, index: int, count: int) -> float:
    ...
```

Для сложных объектов использовать `Protocol`.

---

## 5.2. Недостаточно явные имена методов с side effect

Например:

```python
normalize_slot_content()
```

звучит как безопасная нормализация, но фактически двигает группы.

### Почему это проблема

Разработчик может вызвать метод “просто обновить размер”, а метод изменит layout.

### Рекомендуемый подход

Называть методы по действию:

```python
move_generated_groups_to_slot_origin()
normalize_generated_groups_to_slot_origin()
reposition_slot_content_to_origin()
```

---

## 5.3. Комментарии описывают будущее, но не всегда фиксируют текущий контракт

В docstring-ах часто встречается:

```text
Later it can...
Temporary...
Controller will provide...
Future implementation...
```

Это полезно, но текущему коду не хватает конкретных правил:

```text
Кто владеет activity?
В какой системе координат rect?
Кто рисует group?
Можно ли вызывать start повторно?
Что означает True/False в handle_input?
```

### Рекомендуемый подход

Добавлять комментарии не только о будущем, но и о текущем контракте.

Например:

```python
# Return False when event is consumed.
# Return True when event should continue propagation.
```

---

# 6. Рекомендуемый порядок исправления

## Этап 1. Стабилизировать визуальный фундамент

Сначала исправить:

1. transform pipeline карт;
2. scale/rotate/pivot;
3. координатные системы;
4. двойную отрисовку;
5. draw ownership.

Это затрагивает прежде всего:

- `BotHandActivity`;
- `PlayerHandActivity`.

Причина: если базовый transform нестабилен, все layout-улучшения поверх него будут ненадёжными.

---

## Этап 2. Развести lifecycle и владение

Для каждой вложенной activity решить:

```text
Кто её создаёт?
Кто её запускает?
Кто её завершает?
Может ли она жить дольше родителя?
```

Особенно важно для:

- `CardSelectionActivity`;
- `VisibleCardsHandDecorator`;
- `PlayerTurnActivity`;
- `PlayAreaSlotsActivity`.

---

## Этап 3. Ввести явные модели данных

Для выбора карты и хода игрока перейти от:

```text
selected Group
```

к:

```text
selected card_id / hand_index / command
```

Это критично перед подключением реального `GameController`.

---

## Этап 4. Укрепить layout-систему

Ввести:

```python
layout_dirty = True
```

или layout signature.

Layout должен пересчитываться не только после fixture, а после любого изменения, влияющего на геометрию.

---

## Этап 5. Почистить API и технический долг

После стабилизации архитектуры:

- добавить type hints;
- добавить Protocol;
- удалить мёртвый код;
- усилить валидацию fixture;
- разделить debug/runtime;
- переименовать методы с side effects;
- убрать прямую мутацию внутренних структур.

---

# 7. Короткая итоговая формулировка

Код уже хорошо двигается в сторону Activity-архитектуры, но главная слабость сейчас такая:

```text
Activity слишком много знает о внутренностях других Activity, Frame, Group и Screen.
```

Следующий шаг — не добавлять ещё больше поведения поверх текущего слоя, а закрепить контракты:

```text
кто владеет объектами,
кто их рисует,
в какой системе координат они живут,
какие данные идут в Controller,
а какие остаются только визуальными.
```

Если эти контракты закрепить сейчас, дальше будет гораздо проще подключать настоящую игровую логику, анимации, hover, выбор карт и Controller-driven состояние.
