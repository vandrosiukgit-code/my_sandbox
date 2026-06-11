# Code Review Report: `card_selection_activity(4).py`

## Краткое резюме

`CardSelectionActivity` отвечает за интерактивный выбор карты из руки игрока: отслеживает hover, увеличивает карту под курсором, рассчитывает видимые hit-зоны и возвращает controller-facing context выбранной карты.

Класс в целом выглядит полезно и достаточно изолированно: он не знает правил игры, работает поверх `hand_activity` и делегирует получение контекста карты владельцу руки. Однако в текущем виде есть несколько зон риска:

1. возможная нестабильность hover из-за `rest_states` и пересчета layout;
2. hit-test основан на прямоугольниках, а не на реальной повернутой форме карты;
3. `handle_input()` возвращает `True` для неизвестных событий, что может конфликтовать с цепочкой input-handling;
4. hover-анимация может конфликтовать с обновлением layout руки;
5. `get_generated_group_owner()` содержит неявную поддержку вложенной структуры `hand_activity.hand_activity`;
6. состояние выбранной карты может устаревать после изменения руки;
7. класс одновременно отвечает за input, hover, animation state, hit-test и debug forwarding.

---

## 1. Неочевидная семантика `handle_input()`

```python
if event_type == "hover":
    screen_pos = getattr(input_event, "screen_pos", None)
    if screen_pos is not None:
        self.handle_hover(screen_pos)
    return False
return True
```

Проблема: метод возвращает `False` после обработки hover, но `True` для всех остальных событий.

Если в архитектуре `True` означает «событие обработано / остановить дальнейшую передачу», то `CardSelectionActivity` будет блокировать все события, которые сама не обрабатывает.

Если `True` означает «пропустить дальше», тогда поведение нормальное, но это неочевидно из самого кода.

### Рекомендация

Явно зафиксировать контракт в docstring или переименовать/унифицировать результат:

```python
def handle_input(self, input_event):
    """Return True when input should continue bubbling."""
```

Или наоборот:

```python
def handle_input(self, input_event):
    """Return True when this activity consumed the event."""
```

Сейчас без знания внешнего input pipeline это место выглядит потенциально опасным.

---

## 2. Hover может конфликтовать с layout руки

`update()` каждый кадр вызывает:

```python
self.hand_activity.update(dt)
self.prune_stale_group_state()
self.refresh_rest_states()
self.update_selection_actions(dt)
```

При этом `hand_activity.update(dt)` может пересчитать layout и изменить позиции групп. Затем `refresh_rest_states()` обновляет базовые позиции только для не-hovered групп и групп без активных selection actions.

Потенциальный сценарий:

1. карта находится в hover;
2. layout руки изменился из-за frame resize, scale, card_count или resource change;
3. hovered-карта не обновила `rest_state`, потому что она hovered;
4. при уходе курсора карта возвращается в старую позицию, а не в новую позицию layout.

### Риск

Визуально карта может «прыгать» или возвращаться в устаревшее место.

### Рекомендация

Нужен явный механизм инвалидировать `rest_states`, если layout руки изменился. Например, если у `hand_activity` есть `_last_layout_signature`, можно хранить его в selection activity:

```python
current_signature = getattr(self.hand_activity, "_last_layout_signature", None)
if current_signature != self._last_hand_layout_signature:
    self.rest_states = {}
    self._last_hand_layout_signature = current_signature
```

Либо добавить публичный метод в hand activity:

```python
hand_activity.get_layout_signature()
```

---

## 3. Hit-test использует прямоугольники, а карты повернуты

```python
local_hit_rect = group.local_hit_rect.copy()
local_hit_rect.topleft = self.get_base_position(group)
return group.local_rect_to_screen_rect(local_hit_rect)
```

`get_rest_hit_rect()` строит screen-rect из локального прямоугольника. Но карты в веере, судя по связанным activity, повернуты. Значит прямоугольный hit-test будет приближением.

Это нормально для простого UI, но может давать ложные срабатывания:

- курсор находится в пустом углу повернутой карты, но прямоугольник считает, что карта под курсором;
- соседние повернутые карты перекрываются иначе, чем midpoint-логика по `centerx`;
- чем сильнее угол карты, тем хуже точность.

### Рекомендация

Оставить текущую реализацию как fast approximation, но зафиксировать это в комментарии как осознанное решение.

Если нужна точность, использовать mask/polygon hit-test по повернутой поверхности или хотя бы проверку по `group.rect`/слою после transform.

---

## 4. `get_visible_hit_rects()` режет зоны только по X

```python
cards.sort(key=lambda item: item[1].centerx)
...
left = max(left, (previous_rect.centerx + rect.centerx) // 2)
right = min(right, (rect.centerx + next_rect.centerx) // 2)
```

Метод хорошо подходит для горизонтального веера игрока, где карты перекрываются слева направо. Но он хуже подходит для:

- вертикальных рук;
- рук ботов по бокам;
- веера с сильным поворотом;
- нестандартной ориентации;
- случаев, когда порядок отрисовки не совпадает с `centerx`.

### Риск

Если `CardSelectionActivity` случайно применить не только к нижней руке игрока, hover-зоны будут неправильными.

### Рекомендация

Либо явно ограничить класс нижней интерактивной рукой игрока:

```python
"""Selection activity for bottom player hand only."""
```

Либо вынести hit-zone strategy наружу:

```python
CardSelectionActivity(hand_activity, hit_zone_strategy=HorizontalFanHitZoneStrategy())
```

---

## 5. Edge hysteresis основан на позиции в уже отсортированном списке

```python
if index <= 2 or index >= count - 3:
    return self.HOVER_EDGE_CARD_HYSTERESIS_PIXELS
```

Проблема не критичная, но логика «крайние карты» зависит от сортировки по `centerx`, а не от реального индекса карты в руке.

Если карты могут анимироваться, перестраиваться или иметь необычный порядок, «крайними» могут стать не те карты.

### Рекомендация

Если нужен именно визуальный край — текущая логика нормальна.

Если нужен край по hand index — использовать `get_card_selection_context(group)["hand_index"]`.

---

## 6. Неявная поддержка вложенного owner

```python
def get_generated_group_owner(self):
    if hasattr(self.hand_activity, "generated_groups"):
        return self.hand_activity
    if hasattr(self.hand_activity, "hand_activity"):
        return self.hand_activity.hand_activity
    return None
```

Это выглядит как архитектурный костыль: `CardSelectionActivity` знает, что `hand_activity` может быть оберткой над другой `hand_activity`.

### Риск

Если появятся новые декораторы или цепочки декораторов, метод начнет ломаться или потребует новых `if hasattr(...)`.

### Рекомендация

Ввести единый публичный контракт:

```python
hand_activity.iter_generated_groups()
hand_activity.get_card_selection_context(group)
```

Тогда `CardSelectionActivity` не должен знать про `generated_groups` напрямую:

```python
def iter_card_groups(self):
    if hasattr(self.hand_activity, "iter_generated_groups"):
        return tuple(self.hand_activity.iter_generated_groups())
    return ()
```

---

## 7. `validate_hand_activity()` проверяет не весь фактический контракт

Сейчас проверяются только:

```python
for method_name in ("start", "update", "finish"):
```

Но класс фактически может использовать:

- `iter_generated_groups()`;
- `generated_groups`;
- `hand_activity.hand_activity`;
- `get_card_selection_context()`;
- `draw_debug_overlay()`;
- `draw()`;
- `apply_fixture()`.

Часть из них опциональна, но базовый контракт не описан.

### Рекомендация

Сделать явный protocol-like контракт в комментарии или через `typing.Protocol`:

```python
class SelectableHandActivityProtocol(Protocol):
    started: bool
    def start(self): ...
    def update(self, dt): ...
    def finish(self): ...
    def iter_generated_groups(self): ...
```

Это сильно упростит поддержку декораторов.

---

## 8. `selected_card_context` может устареть

```python
self.selected_card_context = self.get_card_selection_context(card_group)
```

Контекст выбранной карты сохраняется. При изменении руки `prune_stale_group_state()` сбрасывает его только если `group_id` исчез:

```python
if selected_group_id is not None and selected_group_id not in current_ids:
    self.selected_card_context = None
```

Но возможен случай, когда `group_id` остался тем же, а карта/ресурс/hand_index изменились. Например, если группа переиспользуется, но `resource_key` или card identity обновились.

### Риск

Контроллер может получить устаревший `selected_card_context`.

### Рекомендация

При изменении resource/layout/card_count лучше сбрасывать selection context или пересчитывать его по текущей группе.

Минимальный вариант:

```python
if selected_group_id is not None:
    selected_group = current_groups.get(selected_group_id)
    if selected_group is None:
        self.selected_card_context = None
    else:
        self.selected_card_context = self.get_card_selection_context(selected_group)
```

---

## 9. Возможное накопление действий при частом hover

```python
self.selection_actions[group.id] = CardSelectionAction(...)
```

Технически словарь не растет бесконечно, потому что ключ — `group.id`. Но при быстром перемещении курсора постоянно создаются новые `CardSelectionAction`.

Это не обязательно проблема, но при большом количестве hover-событий может создавать лишнюю нагрузку и визуальную дерганность.

### Рекомендация

Можно добавить проверку: если уже есть action к тому же target position/scale, не пересоздавать ее.

Или сделать `CardSelectionAction` переиспользуемым/interruptible.

---

## 10. `restore_non_hovered_groups()` анимирует все карты

```python
for group in self.iter_card_groups():
    if group is hovered_group:
        continue
    self.animate_group_to_rest(group)
```

При каждом изменении hover метод проходит по всем картам и потенциально запускает rest-анимацию для всех, кроме новой hovered.

`animate_group_to_rest()` частично защищает от лишней работы через `is_group_at_rest()`, но все равно для каждой карты вызываются проверки base position/base scale.

Для небольшой руки это нормально. Для большого количества карт можно оптимизировать.

### Рекомендация

Анимировать обратно только предыдущую hovered-карту:

```python
previous_hovered = self.hovered_group
if previous_hovered is not None and previous_hovered is not next_hovered_group:
    self.animate_group_to_rest(previous_hovered)
```

Остальные карты трогать только при явной необходимости.

---

## 11. `draw()` делегирует только debug overlay

```python
def draw(self, screen):
    self.draw_debug_overlay(screen)
```

Это нормально, если сами группы рисует `GameScreen`. Но название `draw()` может вводить в заблуждение: кажется, что activity рисует карты, хотя на самом деле только debug.

### Рекомендация

Уточнить docstring:

```python
def draw(self, screen):
    """Draw selection debug overlays; card groups are drawn by GameScreen."""
```

---

## 12. Сильная связка с внутренними полями `Group`

Класс использует:

```python
group.local_rect
group.local_hit_rect
group.scale_factor
group.local_rect_to_screen_rect(...)
```

Это нормально, если `Group` — часть внутренней архитектуры. Но если API `Group` еще нестабилен, `CardSelectionActivity` будет ломаться при изменении модели координат.

### Рекомендация

Со временем можно добавить в `Group` более высокоуровневый метод:

```python
group.get_screen_hit_rect_at(position=None, scale=None)
```

Тогда selection activity не будет вручную собирать hit rect.

---

## Приоритет исправлений

### Высокий приоритет

1. Проверить контракт `handle_input()` — особенно смысл `True`/`False`.
2. Защититься от устаревших `rest_states` при изменении layout руки.
3. Уточнить, что hit-test рассчитан именно на горизонтальную нижнюю руку игрока.
4. Убрать знание о `hand_activity.hand_activity` из `get_generated_group_owner()` через единый публичный контракт.

### Средний приоритет

1. Сбрасывать или пересчитывать `selected_card_context` при изменении карты в той же группе.
2. Анимировать обратно только предыдущую hovered-карту, а не все группы.
3. Документировать приближенный характер rectangular hit-test.
4. Уточнить назначение `draw()`.

### Низкий приоритет

1. Оптимизировать создание `CardSelectionAction` при частых hover-событиях.
2. Вынести hit-zone calculation в отдельную strategy.
3. Добавить `typing.Protocol` для hand activity.

---

## Главный практический риск

Самая подозрительная зона — связка:

```python
hand_activity.update(dt)
refresh_rest_states()
hovered_group не обновляет rest_state
animate_group_to_rest()
```

Если layout руки изменится во время hover, карта может возвращаться не туда, куда должна. Это особенно вероятно при resize окна, изменении масштаба, изменении количества карт или пересборке visual groups.

---

## Архитектурная рекомендация

`CardSelectionActivity` лучше оставить тонким координатором выбора, а три части постепенно вынести отдельно:

```text
CardSelectionActivity
 ├─ HoverStateController
 ├─ CardHitZoneCalculator
 └─ CardSelectionAnimationController
```

На текущем этапе достаточно хотя бы зафиксировать публичный контракт `hand_activity` и убрать неявные проверки вложенных полей.

---

## Минимальный набор правок

```python
def iter_card_groups(self):
    if hasattr(self.hand_activity, "iter_generated_groups"):
        return tuple(self.hand_activity.iter_generated_groups())
    return ()
```

```python
def update(self, dt):
    if not self.started:
        self.start()
        return

    previous_signature = getattr(self.hand_activity, "_last_layout_signature", None)
    self.hand_activity.update(dt)
    current_signature = getattr(self.hand_activity, "_last_layout_signature", None)

    if previous_signature != current_signature:
        self.rest_states = {}

    self.prune_stale_group_state()
    self.refresh_rest_states()
    self.update_selection_actions(dt)
```

```python
def handle_input(self, input_event):
    """Return False when hover was handled and should not continue bubbling."""
    event_type = getattr(input_event, "type", None)
    if event_type == "hover":
        screen_pos = getattr(input_event, "screen_pos", None)
        if screen_pos is not None:
            self.handle_hover(screen_pos)
        return False
    return True
```

Эти изменения не перестраивают архитектуру полностью, но закрывают самые вероятные источники странного поведения.
