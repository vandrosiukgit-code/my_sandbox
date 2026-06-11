# Отчёт о проблемах в `card_selection_activity.py`

**Предложенное имя файла:** `card_selection_activity_audit_report.md`

## Контекст

Файл содержит `CardSelectionActivity` — высокоуровневую Activity для выбора карты из руки игрока. Она:

- запускает и обновляет `hand_activity`;
- отслеживает hover по картам;
- увеличивает карту под курсором;
- применяет hysteresis, чтобы hover не дрожал;
- запускает `player_turn_activity` по двойному левому клику;
- хранит и обновляет короткие анимации выбора через `CardSelectionAnimation`.

Код компактный и в целом понятный, но в нём есть несколько важных архитектурных и runtime-рисков.

---

## 1. `start()` может повторно запускать `hand_activity`

### Проблема

Метод `start()` всегда вызывает:

```python
super().start()
self.hand_activity.start()
```

При этом `update()` тоже вызывает `self.start()`, если `CardSelectionActivity` ещё не запущена:

```python
if not self.started:
    self.start()
```

Если внешний код уже запускал `hand_activity`, то `CardSelectionActivity.start()` может повторно вызвать `hand_activity.start()`.

### Почему это опасно

Если `hand_activity.start()` не идемпотентный, повторный запуск может:

- пересоздать группы;
- сбросить layout;
- удалить или изменить текущие карты;
- сбросить состояние анимации;
- привести к визуальному скачку.

### Рекомендация

Проверять состояние `hand_activity` перед запуском:

```python
def start(self):
    super().start()
    if not getattr(self.hand_activity, "started", False):
        self.hand_activity.start()
```

---

## 2. `finish()` безусловно завершает `hand_activity`

### Проблема

Метод `finish()` делает:

```python
self.hand_activity.finish()
super().finish()
```

### Почему это опасно

Если `hand_activity` используется не только этой Activity, завершение `CardSelectionActivity` может неожиданно удалить или остановить руку.

Особенно опасно, если `hand_activity` — долгоживущий визуальный режим, а `CardSelectionActivity` — только временная интерактивная надстройка.

### Рекомендация

Явно определить владение:

- если `CardSelectionActivity` владеет `hand_activity`, тогда текущий подход допустим;
- если `hand_activity` живёт дольше выбора карты, `finish()` не должен завершать её автоматически.

Возможный вариант:

```python
def __init__(self, hand_activity, player_turn_activity=None, owns_hand_activity=False):
    ...
    self.owns_hand_activity = owns_hand_activity

def finish(self):
    if self.owns_hand_activity:
        self.hand_activity.finish()
    super().finish()
```

---

## 3. `selected_group` создаётся динамически и не объявлен в `__init__`

### Проблема

В `start_player_turn()` есть:

```python
self.selected_group = selected_group
```

Но в `__init__` поле `selected_group` не создаётся.

### Почему это опасно

Код, который попытается прочитать `activity.selected_group` до выбора карты, получит `AttributeError`.

### Рекомендация

Добавить в `__init__`:

```python
self.selected_group = None
```

---

## 4. `handle_input()` возвращает `False` после выбора, но неясно, что означает `False`

### Проблема

В `handle_input()`:

```python
if input_event.type == "hover":
    self.handle_hover(input_event.screen_pos)
    return False
...
if selected_group is not None:
    self.start_player_turn(selected_group)
    return False
return True
```

### Почему это опасно

Без общего контракта непонятно, что означает результат:

- `False` — событие обработано и дальше не передавать?
- `False` — Activity не заинтересована?
- `True` — продолжить обработку?
- `True` — событие поглощено?

Если в других Activity используется противоположная семантика, ввод начнёт работать непредсказуемо.

### Рекомендация

Зафиксировать контракт в базовом `Activity` и добавить комментарий:

```python
# Return False when event is consumed.
# Return True when event should continue propagation.
```

Или использовать более явные имена/enum.

---

## 5. Нет проверки наличия полей у `input_event`

### Проблема

Код предполагает, что у события всегда есть нужные поля:

```python
input_event.type
input_event.screen_pos
input_event.button
```

### Почему это опасно

Если придёт событие другого типа или неполная структура события, Activity упадёт с `AttributeError`.

### Рекомендация

Если input-система не гарантирует строгий контракт, использовать безопасный доступ:

```python
event_type = getattr(input_event, "type", None)
```

И проверять `screen_pos` только для событий, где он нужен.

---

## 6. Hover работает по rest-hit-rect, а не по фактической текущей геометрии карты

### Проблема

Метод `get_rest_hit_rect()` специально возвращает hit rect на основе базовой позиции:

```python
local_hit_rect = group.local_hit_rect.copy()
local_hit_rect.topleft = group._card_selection_base_position
return group.local_rect_to_screen_rect(local_hit_rect)
```

То есть hover считается по rest-состоянию, а не по текущему положению и масштабу карты во время анимации.

### Почему это может быть хорошо

Это может быть осознанный выбор. Он делает hover стабильнее: карта не начинает менять свою hit-зону во время подъёма и увеличения.

### Почему это может быть проблемой

Визуально пользователь видит увеличенную/поднятую карту, но интерактивная зона остаётся в старом месте.

Возможные симптомы:

- курсор находится над видимой картой, но hover уже пропал;
- увеличенная карта перекрывает соседнюю, но клик выбирает не её;
- double-click по визуально поднятой части карты не срабатывает.

### Рекомендация

Оставить rest-hit-rect для стабильности hover, но отдельно решить, по какой геометрии должен работать double-click:

- по rest-зоне;
- по текущей видимой зоне;
- по расширенной зоне hovered-карты.

Для выбора карты обычно лучше учитывать текущую hovered-карту в первую очередь.

---

## 7. Double-click может выбрать не ту карту при активном hover

### Проблема

При double-click выбор делается так:

```python
selected_group = self.find_card_at(input_event.screen_pos)
```

`find_card_at()` использует visible-hit-rects, основанные на rest-состоянии. Если карта поднята и увеличена, её визуальная область может не совпадать с rest-hit-rect.

### Почему это опасно

Пользователь может дважды кликнуть по визуально увеличенной карте, но алгоритм выберет соседнюю карту или ничего не выберет.

### Рекомендация

При double-click сначала проверять текущую hovered-карту:

```python
if self.hovered_group is not None:
    selected_group = self.hovered_group
else:
    selected_group = self.find_card_at(input_event.screen_pos)
```

Или сделать отдельный метод `find_selectable_card_at()`, который учитывает визуальное состояние hover.

---

## 8. `get_visible_hit_rects()` сортирует карты только по `centerx`

### Проблема

Карты сортируются так:

```python
cards.sort(key=lambda item: item[1].centerx)
```

### Почему это опасно

Это работает для горизонтального веера, где видимость действительно можно аппроксимировать слева направо.

Но если рука будет:

- вертикальной;
- повёрнутой;
- расположенной сверху/снизу экрана;
- иметь нестандартный fan orientation;

то сортировка только по `centerx` станет неправильной.

### Рекомендация

Если `CardSelectionActivity` должна поддерживать только нижнюю горизонтальную руку — добавить это в комментарий.

Если нужно поддерживать разные ориентации, сортировку и clipping нужно делать вдоль оси веера, а не только по `x`.

---

## 9. `get_visible_hit_rects()` использует axis-aligned rect для повернутых карт

### Проблема

Карты в руке могут быть повернуты, но hit detection использует прямоугольники:

```python
group.local_hit_rect
group.local_rect_to_screen_rect(...)
```

И затем clip по вертикальным границам.

### Почему это опасно

Для повернутых карт axis-aligned rect плохо соответствует видимой форме карты.

Симптомы:

- hover срабатывает в пустых углах bounding box;
- hover не срабатывает в визуально видимых местах;
- соседние карты конфликтуют в overlap-зонах.

### Рекомендация

Для простой версии это допустимо.

Для более точного выбора можно использовать:

- polygon hit test по четырём углам карты;
- mask-based hit test;
- приоритет z-order + alpha check;
- упрощённый rotated-rect hit test.

---

## 10. Hysteresis для edge-карт завязан на индекс `<= 2` и `>= count - 3`

### Проблема

Метод:

```python
def get_hysteresis_pixels(self, index, count):
    if index <= 2 or index >= count - 3:
        return self.HOVER_EDGE_CARD_HYSTERESIS_PIXELS
    return self.HOVER_HYSTERESIS_PIXELS
```

### Почему это опасно

Для маленького количества карт почти все карты будут считаться edge-картами.

Например:

- `count = 3`: все карты edge;
- `count = 5`: все карты edge;
- `count = 6`: фактически все карты edge.

Возможно, это нормально, но поведение неочевидное.

### Рекомендация

Сделать правило явнее:

```python
edge_count = min(2, count // 3)
if index < edge_count or index >= count - edge_count:
    ...
```

Или вынести количество edge-карт в константу:

```python
HOVER_EDGE_CARD_COUNT = 3
```

---

## 11. Rest-state хранится прямо на объектах `Group`

### Проблема

Код добавляет временные поля прямо в `group`:

```python
group._card_selection_base_position
group._card_selection_base_scale
```

### Почему это опасно

Это создаёт скрытую связь между `CardSelectionActivity` и внутренним состоянием `Group`.

Проблемы:

- другая Activity может использовать такие же поля;
- состояние может пережить саму Activity;
- трудно отлаживать, кто изменил group;
- при повторном использовании группы старый rest-state может оказаться неактуальным.

### Рекомендация

Хранить rest-state внутри самой `CardSelectionActivity`:

```python
self.rest_states[group.id] = {
    "position": tuple(group.local_rect.topleft),
    "scale": group.scale_factor or 1.0,
}
```

Это сделает владение состоянием явным.

---

## 12. `refresh_rest_states()` может перезаписать rest-state во время внешнего layout-изменения

### Проблема

Каждый `update()` вызывает:

```python
self.refresh_rest_states()
```

Метод перезаписывает rest-state для всех не-hovered и не-анимируемых групп:

```python
self.capture_rest_state(group)
```

### Почему это может быть хорошо

Если `hand_activity` пересчитала layout, rest-state автоматически обновится.

### Почему это может быть опасно

Если другая система временно меняет положение карты не через `selection_animations`, `CardSelectionActivity` может принять это временное положение за новый rest-state.

### Рекомендация

Лучше обновлять rest-state явно после layout-синхронизации руки, а не на каждом кадре.

Например:

- `hand_activity` выставляет dirty-флаг layout;
- `CardSelectionActivity` обновляет rest-state только при изменении layout;
- animation-state и layout-state разделяются.

---

## 13. Анимации индексируются по `group.id`, но группы могут быть пересозданы

### Проблема

`selection_animations` хранится так:

```python
self.selection_animations[group.id] = CardSelectionAnimation(...)
```

Если `hand_activity` пересоздаст группу с тем же `id`, старая анимация может продолжить ссылаться на старый объект `Group`.

### Почему это опасно

Возможны ситуации:

- animation обновляет уже удалённую группу;
- новая группа с тем же id не анимируется;
- старые ссылки мешают garbage collection;
- визуальное состояние рассинхронизируется.

### Рекомендация

После изменения состава групп очищать анимации, которых больше нет среди актуальных объектов.

Примерная идея:

```python
current_ids = {group.id for group in self.iter_card_groups()}
self.selection_animations = {
    group_id: animation
    for group_id, animation in self.selection_animations.items()
    if group_id in current_ids
}
```

Но ещё лучше хранить и сверять сам объект `group`, а не только id.

---

## 14. При уходе курсора со всех карт hovered-группа восстанавливается не сразу очевидно

### Поведение сейчас

Когда курсор уходит со всех карт:

```python
next_hovered_group = self.find_card_at(screen_pos)
```

получается `None`.

Затем:

```python
self.restore_non_hovered_groups(next_hovered_group)
self.hovered_group = next_hovered_group
```

Так как `hovered_group` равен `None`, `restore_non_hovered_groups(None)` восстановит все группы.

### Вывод

Это работает.

### Почему стоит отметить

Логика неочевидная. На первый взгляд может показаться, что старая hovered-карта не восстанавливается. Стоит добавить комментарий, что `hovered_group=None` означает восстановление всех карт.

---

## 15. `player_turn_activity.start()` запускается без передачи выбранной карты

### Проблема

В `start_player_turn()`:

```python
self.selected_group = selected_group
if self.player_turn_activity is not None:
    self.player_turn_activity.start()
```

Выбранная группа сохраняется в `CardSelectionActivity`, но не передаётся в `player_turn_activity`.

### Почему это опасно

Если `player_turn_activity` должна знать, какая карта выбрана, ей придётся:

- иметь ссылку обратно на `CardSelectionActivity`;
- читать `selected_group` снаружи;
- получать выбранную карту через какой-то другой side-channel.

Это делает поток данных неявным.

### Рекомендация

Сделать передачу выбора явной.

Варианты:

```python
self.player_turn_activity.start(selected_group)
```

или:

```python
self.player_turn_activity.set_selected_group(selected_group)
self.player_turn_activity.start()
```

Ещё лучше — выбирать не `Group`, а domain-модель карты или индекс карты, если эта Activity должна инициировать игровой ход.

---

## 16. Activity выбора оперирует visual-only группами, а не игровыми сущностями

### Проблема

Выбор происходит на уровне `Group`:

```python
selected_group = self.find_card_at(input_event.screen_pos)
self.start_player_turn(selected_group)
```

### Почему это опасно

`Group` — визуальная сущность. Она может не иметь прямого отношения к игровой карте.

Если карты пересортируются, пересоздадутся или будут использоваться как visual-only proxy, выбор группы не обязательно означает выбор конкретной карты в `GameController`.

### Рекомендация

Добавить mapping:

```python
group.id -> card_id
```

или:

```python
group -> hand_index
```

И в игровую логику передавать не `Group`, а `card_id` / `hand_index`.

---

## 17. Нет защиты от отсутствия `hand_activity`

### Проблема

`__init__` принимает `hand_activity`, но не валидирует его:

```python
self.hand_activity = hand_activity
```

Дальше код безусловно вызывает:

```python
self.hand_activity.start()
self.hand_activity.update(dt)
self.hand_activity.finish()
```

### Почему это опасно

Если по ошибке передать `None` или несовместимый объект, ошибка появится позже и будет менее понятной.

### Рекомендация

Добавить раннюю проверку:

```python
if hand_activity is None:
    raise ValueError("CardSelectionActivity requires hand_activity")
```

И при необходимости проверить наличие методов `start`, `update`, `finish`.

---

## 18. Не очищаются `hovered_group` и `selection_animations` при `finish()`

### Проблема

`finish()` завершает `hand_activity`, но не очищает состояние выбора:

```python
def finish(self):
    self.hand_activity.finish()
    super().finish()
```

### Почему это опасно

После завершения Activity внутри неё остаются ссылки на группы:

- `hovered_group`;
- `selected_group`, если он был выбран;
- `selection_animations`, которые содержат ссылки на группы через `CardSelectionAnimation`.

Если группы удалены в `hand_activity.finish()`, эти ссылки становятся устаревшими.

### Рекомендация

Очищать состояние:

```python
def finish(self):
    self.hovered_group = None
    self.selected_group = None
    self.selection_animations.clear()
    self.hand_activity.finish()
    super().finish()
```

Если `hand_activity.finish()` удаляет группы, очищение лучше сделать до или сразу после него.

---

# Приоритет исправлений

## Высокий приоритет

1. Явно определить владение `hand_activity`: должна ли `CardSelectionActivity` запускать и завершать её.
2. Добавить `self.selected_group = None` в `__init__`.
3. Решить, должен ли double-click выбирать `hovered_group`, а не заново искать карту по rest-hit-rect.
4. Явно передавать выбранную карту/индекс/ID в `player_turn_activity`.

## Средний приоритет

5. Убрать хранение `_card_selection_base_*` прямо на `Group` и перенести rest-state в `CardSelectionActivity`.
6. Чистить `selection_animations` при пересоздании групп.
7. Проверить контракт `handle_input()` по возвращаемому `True` / `False`.
8. Добавить валидацию `hand_activity` и полей `input_event`.

## Низкий приоритет

9. Уточнить hysteresis для маленького количества карт.
10. Документировать, что clipping hit-зон работает только для горизонтального веера.
11. Улучшить hit detection для повернутых карт.
12. Очистить внутренние ссылки при `finish()`.

---

# Главный вывод

Главная архитектурная проблема файла — смешение двух уровней ответственности:

```text
CardSelectionActivity
-> визуальный hover и анимация
-> запуск/завершение hand_activity
-> выбор visual-only Group
-> запуск player_turn_activity
```

Сейчас выбор карты проходит через визуальную сущность `Group`, а не через явную игровую сущность вроде `card_id` или `hand_index`.

Для прототипа это допустимо, но перед подключением к реальной игровой логике лучше сделать поток данных явным:

```text
screen_pos
-> hovered visual group
-> hand index / card id
-> GameController command
-> PlayerTurnActivity
```

Так `CardSelectionActivity` останется визуально-интерактивным слоем, а не начнёт владеть правилами игры.
