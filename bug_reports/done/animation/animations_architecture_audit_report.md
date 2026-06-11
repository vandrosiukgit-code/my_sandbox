# Отчёт о проблемах в animation-файлах и архитектуре анимаций

**Предложенное имя файла:** `animations_architecture_audit_report.md`

## Контекст

В отчёте рассмотрены три файла:

- `base_animation.py`
- `card_selection_animation.py`
- `move_group_animation.py`

Эти файлы формируют базовую систему визуальных анимаций:

```text
Animation
-> CardSelectionAnimation
-> MoveGroupAnimation
```

По замыслу `Animation` является базовым time-based primitive, а наследники меняют визуальное состояние `Group`: позицию, scale или другие drawable-свойства.

Главная общая проблема: система анимаций уже полезна как минимальный прототип, но пока не имеет достаточно строгих контрактов по координатным системам, владению состоянием, завершению, конфликтующим анимациям и взаимодействию с layout.

---

# 1. Проблемы `base_animation.py`

## 1.1. `dt` не валидируется

### Проблема

В `update()` значение `dt` напрямую добавляется к `elapsed`:

```python
self.elapsed += dt
```

### Почему это опасно

Если `dt` будет:

- отрицательным;
- строкой;
- `None`;
- слишком большим из-за лаг-спайка;

анимация может повести себя непредсказуемо.

Например, отрицательный `dt` может уменьшить `elapsed` и откатить progress назад.

### Рекомендация

Нормализовать `dt`:

```python
dt = max(0.0, float(dt))
```

Для очень больших значений можно добавить clamp:

```python
dt = min(dt, max_frame_dt)
```

---

## 1.2. При `duration = 0` animation вызывает `apply()` дважды

### Проблема

`duration` нормализуется так:

```python
self.duration = max(0.0, float(duration))
```

Если `duration = 0`, то `get_progress()` вернёт `1.0`.

В `update()`:

```python
self.elapsed += dt
self.apply(self.get_progress())

if self.elapsed >= self.duration:
    self.finish()
```

Для duration 0 это значит:

```text
update()
-> apply(1.0)
-> finish()
```

Но наследник в `finish()` тоже может выставить финальное состояние.

Например `CardSelectionAnimation.finish()` и `MoveGroupAnimation.finish()` принудительно выставляют target state.

### Почему это может быть нормально

Финальное состояние будет правильным.

### Почему это может быть проблемой

Если `apply()` в будущем будет иметь side effects, они могут выполниться лишний раз.

### Рекомендация

Для `duration <= 0` можно завершать сразу:

```python
if self.duration <= 0:
    self.apply(1.0)
    self.finish()
    return
```

Или принять текущее поведение как контракт, но явно описать его.

---

## 1.3. `finish()` не вызывает `apply(1.0)` в базовом классе

### Проблема

Базовый `finish()` только меняет флаги:

```python
self._finished = True
self.started = False
```

Он не гарантирует, что animation окажется в финальном состоянии.

Сейчас наследники `CardSelectionAnimation` и `MoveGroupAnimation` сами выставляют final state в `finish()`, но базовый класс этого не требует.

### Почему это опасно

Новый наследник может забыть переопределить `finish()`, и тогда при завершении состояние может остаться не точно в target.

### Рекомендация

Рассмотреть шаблон:

```python
def finish(self):
    self.apply(1.0)
    self._finished = True
    self.started = False
```

Но важно избежать двойного применения `apply(1.0)` у наследников. Лучше разделить lifecycle hook:

```python
def complete(self):
    self.apply(1.0)

def finish(self):
    self.complete()
    self._finished = True
    self.started = False
```

---

## 1.4. Нет callbacks/events завершения

### Проблема

После завершения animation только выставляется `_finished`.

Нет механизма:

- `on_start`;
- `on_update`;
- `on_finish`;
- callback после завершения;
- уведомления animation manager.

### Почему это ограничивает архитектуру

Сейчас внешний код должен polling-ом проверять:

```python
if animation.is_finished():
    ...
```

Это допустимо для простого прототипа, но усложнит цепочки анимаций:

```text
поднять карту
-> переместить на стол
-> перевернуть
-> обновить layout
-> передать ход
```

### Рекомендация

Добавить optional callback:

```python
def __init__(self, duration=0.0, on_finish=None):
    self.on_finish = on_finish
```

И вызывать его при завершении.

---

## 1.5. Нет `cancel()` / `reset()` / `pause()`

### Проблема

Сейчас animation можно только:

- start;
- update;
- finish.

Нет отдельного понятия cancellation.

### Почему это важно

В UI-анимациях часто нужно:

- отменить hover animation;
- заменить текущую animation новой;
- сбросить animation без применения финального target;
- поставить на pause.

`finish()` означает “дойти до финального состояния”, а `cancel()` обычно означает “прекратить без обязательного target state”.

### Рекомендация

Добавить хотя бы:

```python
def cancel(self):
    self._finished = True
    self.started = False
```

И использовать `finish()` только как successful completion.

---

## 1.6. Базовый `apply()` молча ничего не делает

### Проблема

```python
def apply(self, progress):
    _ = progress
```

Если наследник забудет переопределить `apply()`, animation будет “работать”, но ничего не менять.

### Почему это опасно

Ошибка будет тихой.

### Рекомендация

Сделать базовый метод абстрактным:

```python
from abc import ABC, abstractmethod

class Animation(ABC):
    @abstractmethod
    def apply(self, progress):
        ...
```

Или бросать ошибку:

```python
raise NotImplementedError
```

---

# 2. Проблемы `card_selection_animation.py`

## 2.1. Анимация меняет scale и position, но не синхронизирует parent frame origins

### Проблема

Animation делает:

```python
self.group.set_scale_factor(scale)
self.group.set_local_position(x, y)
```

Но в других частях проекта при изменении local position часто вручную обновляется:

```python
frame.group_origins[group.id] = group.local_rect.topleft
```

В `CardSelectionAnimation` этого нет.

### Почему это опасно

Если `frame.group_origins` используется как источник layout/origin-состояния, animation может визуально передвинуть группу, но frame-origin останется старым.

Симптомы:

- после анимации layout snap-нет карту обратно;
- frame/debug считает старую позицию;
- collision или hit rect может использовать устаревший origin;
- следующая activity берёт неправильную base position.

### Рекомендация

Лучше убрать необходимость ручной синхронизации `frame.group_origins`.

Но если текущая архитектура требует её, нужен публичный API:

```python
group.set_local_position(x, y, sync_parent=True)
```

или:

```python
group.sync_origin_with_parent_frame()
```

Анимация не должна напрямую знать про `frame.group_origins`, но система должна гарантировать синхронизацию.

---

## 2.2. Анимация хранит `from_position` и `from_scale` после первого start

### Проблема

В `start()`:

```python
if self.from_position is None:
    self.from_position = tuple(self.group.local_rect.topleft)
if self.from_scale is None:
    self.from_scale = self.get_group_scale(self.group)
```

После первого запуска `from_position` и `from_scale` больше не `None`.

Если ту же animation instance запустить повторно, она будет стартовать со старой позиции и старого scale.

### Почему это опасно

Если animation object будет переиспользован, поведение будет неправильным.

### Рекомендация

Либо явно запретить переиспользование animation instance, либо хранить original values отдельно.

Например:

```python
self._explicit_from_position = from_position is not None
```

И на каждом start переснимать from-state, если он не был задан явно.

---

## 2.3. Нет проверки, что `group` совместим

### Проблема

Animation ожидает, что у group есть:

```python
local_rect
scale_factor
set_scale_factor()
set_local_position()
```

Но совместимость не проверяется.

### Почему это опасно

Если передать не тот объект, ошибка появится во время animation update.

### Рекомендация

Добавить раннюю валидацию в `__init__` или type hints / Protocol:

```python
class ScalableLocalGroupLike(Protocol):
    local_rect: Rect
    scale_factor: float | None
    def set_scale_factor(self, value: float) -> None: ...
    def set_local_position(self, x: float, y: float) -> None: ...
```

---

## 2.4. `to_scale` не валидируется

### Проблема

```python
self.to_scale = float(to_scale)
```

Можно передать:

```python
to_scale = 0
to_scale = -1
```

### Почему это опасно

Нулевой или отрицательный scale почти наверняка сломает визуальное состояние.

### Рекомендация

Валидировать:

```python
if self.to_scale <= 0:
    raise ValueError("to_scale must be positive")
```

То же касается `from_scale`, если он задан явно.

---

## 2.5. Позиция нормализуется в int, но interpolate возвращает float

### Проблема

`normalize_position()` возвращает int:

```python
return int(round(float(position[0]))), int(round(float(position[1])))
```

Но `interpolate()` возвращает float:

```python
return start + (end - start) * progress
```

Затем:

```python
self.group.set_local_position(x, y)
```

получает float.

### Почему это может быть нормально

Если `set_local_position()` умеет принимать float и сам округляет — всё хорошо.

### Почему это может быть проблемой

Если `Group` ожидает int, внутри могут появляться неявные округления или floating drift.

### Рекомендация

Выбрать контракт:

```text
positions are floats during animation
```

или:

```text
positions are rounded to int at every frame
```

Если нужен pixel-perfect UI, лучше округлять в animation:

```python
self.group.set_local_position(round(x), round(y))
```

---

## 2.6. Scale и position меняются в фиксированном порядке

### Проблема

```python
self.group.set_scale_factor(scale)
self.group.set_local_position(x, y)
```

### Почему это может быть важно

Если `set_scale_factor()` меняет `local_rect`, hit rect или pivot, то последующий `set_local_position()` может иметь один эффект.

Если порядок поменять:

```python
set_local_position()
set_scale_factor()
```

эффект может быть другой.

### Рекомендация

Закрепить контракт в `Group`:

```text
set_scale_factor does not change local_rect.topleft
```

или:

```text
set_scale_factor may change rect size but preserves top-left
```

Без этого animation может вести себя по-разному в зависимости от реализации Group.

---

# 3. Проблемы `move_group_animation.py`

## 3.1. Докстринг говорит “screen positions”, а другие animation используют local positions

### Проблема

`MoveGroupAnimation` описана так:

```text
Move a Group between two screen positions over time.
```

И использует:

```python
self.from_position = tuple(self.group.rect.topleft)
self.group.set_position(x, y)
```

А `CardSelectionAnimation` использует:

```python
group.local_rect.topleft
group.set_local_position(...)
```

### Почему это серьёзно

В системе одновременно существуют две похожие animation:

```text
CardSelectionAnimation — local position
MoveGroupAnimation     — screen position
```

Но это не отражено в имени.

### Рекомендация

Переименовать классы или явно разделить:

```python
MoveGroupScreenAnimation
MoveGroupLocalAnimation
```

Или сделать один универсальный класс:

```python
MoveGroupAnimation(coordinate_space="screen" | "local")
```

Главное — координатная система должна быть видна в API.

---

## 3.2. Возможен конфликт screen/local координат

### Проблема

Animation берёт:

```python
self.group.rect.topleft
```

и применяет:

```python
self.group.set_position(x, y)
```

Если `group.rect` — screen rect, а `set_position()` ожидает screen position, всё хорошо.

Но если `set_position()` на самом деле работает в другой системе координат или пересчитывает local position относительно parent frame, возможна ошибка.

### Рекомендация

Зафиксировать контракт:

```text
group.rect is screen-space rect
group.set_position(x, y) accepts screen-space coordinates
```

Если это не всегда так, нужен отдельный adapter.

---

## 3.3. `normalize_position()` менее устойчив, чем в `CardSelectionAnimation`

### Проблема

В `MoveGroupAnimation`:

```python
return int(position[0]), int(position[1])
```

В `CardSelectionAnimation`:

```python
return int(round(float(position[0]))), int(round(float(position[1])))
```

### Почему это проблема

Одинаковые по смыслу helper-методы ведут себя по-разному:

- один принимает float-like строки;
- другой нет;
- один округляет;
- другой отбрасывает дробную часть;
- один может дать более понятное поведение;
- другой может молча floor/truncate.

### Рекомендация

Вынести общую нормализацию позиции в utility:

```python
normalize_position_pair(position) -> tuple[int, int]
```

И использовать одинаково.

---

## 3.4. `interpolate()` округляет каждый кадр

### Проблема

```python
return round(start + (end - start) * progress)
```

### Почему это может быть нормально

Для pixel-perfect screen movement это хорошо.

### Почему это может быть проблемой

При медленных анимациях движение может быть ступенчатым.

`CardSelectionAnimation` возвращает float, а `MoveGroupAnimation` возвращает rounded int. Это ещё одно различие поведения.

### Рекомендация

Определить общий подход:

```text
Animation stores float positions, Group rounds on draw
```

или:

```text
Animation rounds positions every frame
```

Сейчас подходы смешаны.

---

## 3.5. Анимация хранит `from_position` после первого start

### Проблема

Как и `CardSelectionAnimation`, класс переснимает стартовую позицию только если `from_position is None`.

После первого запуска instance становится stateful и повторный start может использовать старый start point.

### Рекомендация

Явно запретить reuse или реализовать reset/restart semantics.

---

## 3.6. Нет проверки совместимости `group`

### Проблема

Animation ожидает:

```python
group.rect
group.set_position()
```

Но не проверяет это.

### Рекомендация

Добавить type hints / Protocol:

```python
class ScreenMovableGroupLike(Protocol):
    rect: Rect
    def set_position(self, x: int, y: int) -> None: ...
```

---

# 4. Обобщённые архитектурные проблемы animation-подхода

## 4.1. Нет единой модели координат для анимаций

Сейчас есть минимум две координатные модели:

```text
local position:
    CardSelectionAnimation
    group.local_rect
    group.set_local_position()

screen position:
    MoveGroupAnimation
    group.rect
    group.set_position()
```

Но это различие не отражено достаточно явно в названиях и API.

### Риск

Разработчик может использовать screen animation там, где нужна local animation, и объект уедет не туда.

### Рекомендация

Сделать coordinate-space явным:

```python
MoveGroupLocalAnimation
MoveGroupScreenAnimation
```

или:

```python
MoveGroupAnimation(group, to_position, coordinate_space="local")
```

---

## 4.2. Анимации напрямую мутируют `Group`

Каждая animation напрямую вызывает методы group:

```python
group.set_position(...)
group.set_local_position(...)
group.set_scale_factor(...)
```

### Почему это нормально

Для маленькой системы это простой и понятный способ.

### Почему это станет проблемой

Если одновременно работают:

- layout system;
- hover animation;
- selection animation;
- card move animation;
- frame normalization;
- controller-driven state update;

они могут перезаписывать состояние друг друга.

### Рекомендация

Ввести animation owner/manager, который знает:

```text
какие свойства сейчас анимируются
какие animation конфликтуют
какая animation имеет приоритет
что делать при cancel/replace
```

Например:

```python
animation_manager.play(group_id, "position", animation, replace=True)
animation_manager.play(group_id, "scale", animation, replace=True)
```

---

## 4.3. Нет property-level conflict management

Сейчас две animation могут одновременно менять одно и то же свойство:

```text
MoveGroupAnimation меняет position
CardSelectionAnimation меняет position и scale
layout пересчитывает position
```

### Риск

Результат будет зависеть от порядка update.

Например:

```text
layout поставил карту на место
hover animation подняла карту
следующий layout снова поставил карту на место
animation снова подняла карту
```

Это даст дрожание или snap.

### Рекомендация

Разделить источники состояния:

```text
layout base state
animation offset state
rendered state = base + animation offset
```

Или хотя бы сделать animation manager с exclusive lock по property:

```text
group_id + property_name -> active animation
```

---

## 4.4. Нет явного distinction между base layout и animated visual state

Сейчас animation меняет саму позицию group.

Но для UI часто лучше разделить:

```text
base_position      — где объект должен быть по layout
visual_offset      — временный animation offset
rendered_position  — base_position + visual_offset
```

### Почему это важно

Тогда layout может обновляться независимо от animation.

Например:

```text
рука пересчитала base positions
hover animation всё ещё добавляет lift offset
```

Сейчас animation и layout пишут в одно и то же поле.

### Рекомендация

Добавить слой transform state:

```python
group.base_local_position
group.visual_offset
group.visual_scale_multiplier
```

Или создать `VisualTransform`:

```python
group.transform.base_position
group.transform.animation_position_offset
group.transform.scale
```

---

## 4.5. Animation lifecycle не интегрирован с Activity lifecycle

Animation имеет:

```python
start()
update()
finish()
```

Activity тоже имеет:

```python
start()
update()
finish()
```

Но нет общего менеджера, который связывает их.

### Риск

Если Activity завершилась, animation может всё ещё держать ссылку на group.

Если group удалена, animation может продолжить обновлять устаревший объект.

### Рекомендация

При `Activity.finish()`:

```python
cancel_all_animations_owned_by_activity()
```

Или animation manager должен автоматически удалять анимации для удалённых groups.

---

## 4.6. Нет безопасного поведения при удалении group во время animation

Animation хранит прямую ссылку:

```python
self.group = group
```

Если group удалена из frame или screen registry, animation всё равно может продолжить её менять.

### Рекомендация

Animation manager должен проверять:

```python
group still alive
group still registered
group parent frame still exists
```

Или group должна иметь флаг:

```python
group.destroyed
```

---

## 4.7. Нет единой easing-системы

Оба наследника имеют одинаковый `ease_out()`:

```python
return 1.0 - (1.0 - progress) * (1.0 - progress)
```

### Почему это проблема

Дублирование небольшое, но оно показывает, что easing лучше вынести в общую utility.

### Рекомендация

Создать:

```python
animations/easing.py
```

Например:

```python
def ease_out_quad(progress: float) -> float:
    progress = clamp01(progress)
    return 1.0 - (1.0 - progress) ** 2
```

---

## 4.8. Нет общей interpolation utility

Оба наследника имеют собственный `interpolate()`.

Один возвращает float:

```python
return start + (end - start) * progress
```

Другой возвращает rounded int:

```python
return round(start + (end - start) * progress)
```

### Рекомендация

Вынести:

```python
lerp_float(start, end, progress)
lerp_int(start, end, progress)
```

И использовать явно.

---

## 4.9. Animation instances являются stateful и плохо подходят для reuse

Animation хранит:

```python
elapsed
started
_finished
from_position
from_scale
```

Это нормально.

Но тогда нужно явно считать:

```text
Animation instance is one-shot.
```

Сейчас это не зафиксировано.

### Рекомендация

Документировать:

```text
Animation objects are one-shot; create a new instance for every run.
```

Или реализовать `reset()` / `restart()`.

---

## 4.10. Нет typed target properties

Сейчас каждая animation сама решает, что она меняет.

Например:

```text
CardSelectionAnimation:
    local_position
    scale

MoveGroupAnimation:
    screen_position
```

Но нигде не указано в машинно-читаемом виде, какие properties заняты.

### Рекомендация

Добавить свойство:

```python
animated_properties = ("local_position", "scale")
```

Для `MoveGroupAnimation`:

```python
animated_properties = ("screen_position",)
```

Это поможет animation manager-у предотвращать конфликты.

---

# 5. Приоритет исправлений

## Высокий приоритет

1. Явно разделить local-position и screen-position animations.
2. Решить, кто синхронизирует изменения group position с parent frame / frame origins.
3. Ввести cancel semantics для animations.
4. Зафиксировать, что animation instance является one-shot, или добавить reset/restart.
5. Добавить защиту от конфликтующих animations, хотя бы на уровне Activity.

## Средний приоритет

6. Вынести easing и interpolation в общие utilities.
7. Добавить валидацию `dt`, `to_scale`, `from_scale`, positions.
8. Добавить callbacks/events завершения.
9. Добавить Protocol/type hints для group-like объектов.
10. Решить, должны ли positions быть float или int во время animation.

## Низкий приоритет

11. Сделать базовый `Animation.apply()` абстрактным.
12. Добавить `pause()` при необходимости.
13. Унифицировать normalize_position между animation-классами.
14. Добавить machine-readable `animated_properties`.
15. Документировать lifecycle: start/update/finish/cancel/reuse.

---

# 6. Рекомендуемая целевая архитектура

## 6.1. Базовый Animation

```python
class Animation:
    duration: float
    elapsed: float
    started: bool
    finished: bool
    cancelled: bool
    animated_properties: tuple[str, ...]

    def start(self): ...
    def update(self, dt: float): ...
    def apply(self, progress: float): ...
    def finish(self): ...
    def cancel(self): ...
```

---

## 6.2. Явные coordinate-space классы

```python
MoveGroupLocalAnimation
MoveGroupScreenAnimation
ScaleGroupAnimation
CardSelectionHoverAnimation
```

Или единый класс с явным параметром:

```python
MoveGroupAnimation(
    group,
    to_position,
    coordinate_space="local",
)
```

---

## 6.3. AnimationManager

Минимальный менеджер:

```python
class AnimationManager:
    def play(self, animation, replace_conflicts=True): ...
    def update(self, dt): ...
    def cancel_for_group(self, group_id): ...
    def cancel_for_activity(self, activity): ...
```

Он должен знать:

```text
group id
activity owner
animated properties
conflict policy
```

---

## 6.4. Разделение layout state и animated state

Более зрелый подход:

```text
base layout position
+ animation offset
+ animation scale
= rendered transform
```

Тогда layout и animation не будут перезаписывать друг друга.

---

# 7. Главный вывод

Текущая animation-система хороша как минимальный прототип:

```text
Animation задаёт время
CardSelectionAnimation меняет local position + scale
MoveGroupAnimation меняет screen position
```

Но перед ростом проекта нужно стабилизировать архитектурные контракты.

Самые важные вопросы:

```text
В какой системе координат работает animation?
Кто имеет право менять position/scale group?
Что происходит, если две animation меняют одно свойство?
Что происходит, если layout обновился во время animation?
Что происходит, если group удалили во время animation?
Animation можно переиспользовать или она one-shot?
```

Если эти правила не закрепить сейчас, то при добавлении hover, выбора карты, перемещения на стол, возврата карты, flip-анимаций и controller-driven состояния появятся трудноуловимые баги: дрожание, snap-back, двойные движения, устаревшие ссылки и рассинхронизация layout с визуальным состоянием.
