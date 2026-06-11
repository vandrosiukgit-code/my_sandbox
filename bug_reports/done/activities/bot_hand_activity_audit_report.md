# Отчёт о проблемах в `bot_hand_activity.py`

**Предложенное имя файла:** `bot_hand_activity_audit_report.md`

## Контекст

Файл содержит класс `BotHandActivity` — долгоживущий визуальный режим руки бота/игрока. Он создаёт visual-only группы закрытых карт, раскладывает их веером внутри `frame`, поворачивает карты, управляет количеством отображаемых карт и удаляет созданные группы при завершении.

Основные зоны риска в текущей реализации:

- смешение масштабирования surface, группы и локальных координат frame;
- потенциально неправильный расчёт pivot при повороте;
- возможная двойная отрисовка групп;
- жёсткая зависимость от `group.layers[0]`;
- неполное обновление визуального состояния при изменении layout или ресурсов.

---

## 1. `scale_surface()` объявлен, но не используется

### Проблема

В классе есть метод `scale_surface()`, который масштабирует `pygame.Surface`, но в текущем коде он нигде не вызывается.

При этом в `apply_card_transform()` используется другой подход:

```python
base_surface = group._bot_hand_base_frames[0]
rotated_surface = pygame.transform.rotate(base_surface, -angle_degrees)

group.layers[0].frames = [rotated_surface]
group.layers[0].position = (0, 0)
group.set_scale_factor(self.scale_factor)
```

То есть карта сначала поворачивается как исходная surface, а масштаб применяется уже на уровне `Group`.

### Почему это опасно

Математика pivot и размеров становится неоднозначной:

- `base_surface.get_size()` — размер исходной surface;
- `rotated_surface.get_size()` — размер повернутой, но ещё не масштабированной surface;
- `group.set_scale_factor()` может менять фактический визуальный размер;
- `set_local_rect()` получает размеры немасштабированной `rotated_surface`.

Из-за этого карта может визуально не попадать своим pivot в рассчитанную точку веера.

### Рекомендация

Выбрать один источник масштаба.

Предпочтительный вариант для упрощения геометрии:

1. масштабировать исходную surface;
2. вращать уже масштабированную surface;
3. считать pivot по реально используемой surface;
4. устанавливать `group.set_scale_factor(1.0)`.

---

## 2. Возможный неправильный знак угла при расчёте pivot

### Проблема

Surface поворачивается с отрицательным углом:

```python
rotated_surface = pygame.transform.rotate(base_surface, -angle_degrees)
```

Но pivot-offset считается с положительным углом:

```python
rotated_vector = bottom_center_from_source_center.rotate(angle_degrees)
```

### Почему это опасно

Если система координат и направление поворота не компенсируют друг друга, pivot будет рассчитан зеркально относительно фактического поворота surface.

Симптомы:

- карта смещается при повороте;
- нижний центр карты не остаётся на дуге веера;
- чем больше угол, тем заметнее ошибка.

### Рекомендация

Проверить замену:

```python
rotated_vector = bottom_center_from_source_center.rotate(-angle_degrees)
```

Проверять лучше на одной карте с углами `45`, `90`, `-45`, чтобы визуально увидеть, где находится нижний центр.

---

## 3. Возможная двойная отрисовка generated-групп

### Проблема

В `add_generated_group()` группа добавляется во `frame`:

```python
group.set_parent_frame(self.frame)
self.generated_groups.append(group)
self.frame.add_group_id(group.id)
```

Но `BotHandActivity.draw()` также рисует эти группы напрямую:

```python
for group in self.generated_groups:
    group.draw(screen)
```

### Почему это опасно

Если `Frame` сам отрисовывает все группы из `group_id`, generated-карты будут рисоваться дважды.

Возможные симптомы:

- визуальное утолщение/затемнение карт;
- странный порядок слоёв;
- ощущение дублирования;
- некорректная отладочная рамка;
- сложные баги при hover/selection в будущем.

### Рекомендация

Определить одного владельца отрисовки:

#### Вариант A: рисует `Activity`

Тогда не добавлять generated-группы в обычный список отрисовки frame.

#### Вариант B: рисует `Frame`

Тогда убрать ручную отрисовку из `BotHandActivity.draw()`.

---

## 4. Жёсткая зависимость от `group.layers[0]`

### Проблема

Код напрямую обращается к первому слою:

```python
group.layers[0].frames = [rotated_surface]
group.layers[0].position = (0, 0)
```

При этом в классе есть параметр:

```python
card_layer_name="card_back"
```

Но после создания группы слой по имени фактически не используется.

### Почему это опасно

Если структура `Group` изменится, или у карты появятся дополнительные слои, код может начать менять не тот слой.

Например:

- слой тени окажется первым;
- слой карты окажется вторым;
- появится декоративный overlay;
- порядок слоёв поменяется внутри `Group.create_group()`.

### Рекомендация

Получать слой по имени, а не по индексу.

Примерная идея:

```python
card_layer = group.get_layer(self.card_layer_name)
card_layer.frames = [rotated_surface]
card_layer.position = (0, 0)
```

Если метода `get_layer()` нет, стоит добавить его в `Group`.

---

## 5. `normalize_scale_factor()` не валидирует значение

### Проблема

Сейчас метод выглядит так:

```python
@staticmethod
def normalize_scale_factor(value):
    if value is None:
        return None
    return float(value)
```

Он допускает некорректные значения:

```python
scale_factor = 0
scale_factor = -1
scale_factor = "abc"
```

### Почему это опасно

- `0` может сделать карту невидимой или сломать расчёты;
- отрицательный масштаб может привести к непредсказуемой геометрии;
- строка, которую нельзя привести к `float`, вызовет `ValueError` в неподходящем месте.

### Рекомендация

Явно проверять значение:

```python
@staticmethod
def normalize_scale_factor(value):
    if value is None:
        return None

    value = float(value)
    if value <= 0:
        raise ValueError("scale_factor must be positive")

    return value
```

---

## 6. `card_resource_provider` не обновляет уже созданные группы

### Проблема

Метод `get_card_resource_key()` поддерживает динамический provider:

```python
if self.card_resource_provider is not None:
    return self.card_resource_provider(index)
return self.resource_key
```

Но `sync_visual_groups()` только добавляет или удаляет группы по количеству. Если provider начнёт возвращать другой ресурс для уже существующего индекса, старая группа не пересоздастся.

### Пример

Было:

```python
index 0 -> "card_back_red"
```

Стало:

```python
index 0 -> "card_back_blue"
```

Если количество карт не изменилось, визуальная группа останется со старым ресурсом.

### Рекомендация

Либо зафиксировать контракт: `card_resource_provider` используется только при создании группы.

Либо хранить resource key на группе и пересоздавать/обновлять группу, если key изменился.

---

## 7. Изменение `resource_key` обработано только через `apply_fixture()`

### Проблема

В `apply_fixture()` есть корректная логика очистки групп при смене `resource_key`:

```python
if resource_key != self.resource_key:
    self.clear_generated_groups()
    self.resource_key = resource_key
```

Но если внешний код напрямую изменит:

```python
activity.resource_key = "new_back"
activity.set_card_count(5)
```

существующие группы не будут пересозданы.

### Почему это опасно

Публичное поле `resource_key` можно изменить в обход внутренней логики синхронизации.

### Рекомендация

Добавить явный метод:

```python
def set_resource_key(self, resource_key):
    if resource_key != self.resource_key:
        self.clear_generated_groups()
        self.resource_key = resource_key
        self.sync_visual_groups()
        self.apply_fan_layout()
```

И считать прямую мутацию `activity.resource_key = ...` нежелательной.

---

## 8. Неполная очистка generated-групп

### Проблема

Очистка выглядит так:

```python
for group in self.generated_groups:
    self.frame.remove_group_id(group.id)
    self.frame.group_origins.pop(group.id, None)
self.generated_groups = []
```

### Почему это может быть проблемой

Если группы также хранятся в глобальном registry, scene manager, layout manager или другом контейнере, они могут остаться в памяти или продолжить участвовать в логике.

### Рекомендация

Проверить архитектуру `Frame` / `Group`.

Если есть внешний registry, очистка должна удалять generated-группы оттуда тоже.

---

## 9. `update()` не пересчитывает layout после изменений frame

### Проблема

Сейчас `update()` почти ничего не делает:

```python
def update(self, dt):
    _ = dt
    if not self.started:
        self.start()
```

Layout пересчитывается только при:

- `start()`;
- `set_card_count()`;
- `apply_fixture()`.

### Почему это опасно

Если после старта изменится:

- размер frame;
- `frame.content_rect`;
- экранный scale;
- положение frame;
- layout родительского контейнера;

веер не будет автоматически пересчитан.

### Рекомендация

Добавить dirty-флаг или отслеживание последнего состояния layout.

Примерная идея:

```python
def update(self, dt):
    if not self.started:
        self.start()
        return

    current_signature = (
        self.frame.content_rect.copy(),
        self.get_frame_screen_scale(),
        self.scale_factor,
        self.radius,
        self.center_offset,
    )

    if current_signature != self._last_layout_signature:
        self.apply_fan_layout()
        self._last_layout_signature = current_signature
```

---

## 10. Возможная путаница между `local_rect` и `rect`

### Проблема

В layout устанавливается `local_rect`:

```python
group.set_local_rect(...)
```

Но debug bounds считаются через `group.rect`:

```python
bounds = group.rect.copy() if bounds is None else bounds.union(group.rect)
```

### Почему это опасно

Если `group.rect` и `group.local_rect` находятся в разных системах координат, debug-рамка может быть смещена.

Особенно это важно, потому что `draw_fan_rect()` рисует прямо на `screen`:

```python
pygame.draw.rect(screen, self.debug_fan_rect_color, bounds, 2)
```

### Рекомендация

Проверить контракт `Group`:

- `local_rect` — координаты внутри frame;
- `rect` — экранные координаты;
- или оба в одной системе координат.

Если `rect` не экранный, перед debug-отрисовкой нужно конвертировать координаты.

---

## 11. Сомнительная формула для маленького количества карт

### Проблема

Для `count <= reference_card_count` используется:

```python
occupied_angle = reference_step * count
return occupied_angle, reference_step
```

А угол карты считается так:

```python
return -occupied_angle / 2 + angle_step / 2 + index * angle_step
```

Для `count = 2` это даст две карты по центрам слотов внутри сектора:

```text
- reference_step / 2
+ reference_step / 2
```

Это логично.

Но для `count = 1` метод возвращает:

```python
return self.max_total_angle / self.reference_card_count, 0.0
```

А затем `calculate_card_angle()` возвращает `0.0`.

То есть `occupied_angle` для одной карты фактически не используется.

### Почему это не критично

Сейчас это не ломает код.

### Почему стоит поправить

Возврат ненужного `occupied_angle` для одной карты может запутывать при поддержке.

### Рекомендация

Сделать явно:

```python
if count <= 1:
    return 0.0, 0.0
```

---

## 12. Потенциальный конфликт ответственности между `BotHandActivity` и `Frame`

### Проблема

`BotHandActivity` одновременно:

- создаёт `Group`;
- добавляет их во `Frame`;
- управляет `frame.group_origins`;
- отрисовывает группы;
- удаляет группы из frame;
- хранит собственный список generated-групп.

Это делает Activity не просто режимом поведения, а частично владельцем визуальной сцены.

### Почему это опасно

В будущем это усложнит:

- hover;
- selection;
- z-order;
- drag-and-drop;
- анимации;
- обновление layout;
- синхронизацию с `GameController`.

### Рекомендация

Явно определить архитектурный контракт:

- `BotHandActivity` только рассчитывает layout и команды;
- `Frame` владеет группами и отрисовкой;
- или `BotHandActivity` полностью владеет generated-группами и не регистрирует их как обычные frame-группы.

Сейчас выбран смешанный вариант.

---

# Приоритет исправлений

## Высокий приоритет

1. Разобраться с масштабированием: surface-scale vs group-scale.
2. Проверить знак угла в `calculate_rotated_pivot_offset()`.
3. Убрать риск двойной отрисовки.
4. Перестать обращаться к `group.layers[0]` напрямую.

## Средний приоритет

5. Добавить валидацию `scale_factor`.
6. Добавить корректную смену `resource_key`.
7. Обработать изменение ресурсов от `card_resource_provider`.
8. Проверить полную очистку generated-групп.

## Низкий приоритет

9. Упростить `calculate_fan_angles()` для `count = 1`.
10. Проверить debug-рамку и систему координат `rect` / `local_rect`.
11. Добавить dirty-флаг для пересчёта layout при изменении frame.

---

# Главный вывод

Самая вероятная причина будущих визуальных багов — блок `apply_card_transform()`.

В нём одновременно смешаны:

- поворот surface;
- масштабирование группы;
- локальный масштаб относительно frame;
- расчёт pivot по повернутой surface;
- установка `local_rect` с размерами немасштабированной surface.

Чтобы сделать поведение предсказуемым, стоит упростить pipeline трансформации:

```text
base surface
-> scale surface
-> rotate scaled surface
-> calculate pivot on rotated scaled surface
-> set group local rect
-> draw without additional group scale
```

Это уменьшит количество скрытых поправок и сделает веер намного проще для отладки.
