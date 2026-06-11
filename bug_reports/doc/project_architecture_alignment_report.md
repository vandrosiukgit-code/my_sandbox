# Отчёт: совершенствование архитектуры проекта и критические отклонения кода от документации

**Предложенное имя файла:** `project_architecture_alignment_report.md`

## Назначение отчёта

Этот документ сопоставляет текущий код проекта с архитектурной документацией и фиксирует:

1. критические отклонения кода от задокументированных принципов;
2. причины, почему эти отклонения опасны;
3. пути совершенствования текущей архитектуры;
4. приоритетный порядок исправлений;
5. уточнения, которые стоит добавить в документацию.

Документ опирается на следующие архитектурные материалы:

- `architectural_manifesto_v6.2.md`
- `architecture.md`
- `current_architecture_snapshot.md`
- `gui_manifest.md`
- `visual_input_flow.md`

И на ранее просмотренные группы файлов:

- Activity-файлы;
- Animation-файлы;
- `render_engine.py`.

---

# 1. Краткий архитектурный диагноз

Документация проекта уже задаёт достаточно сильную и цельную архитектуру:

```text
RenderEngine       — Pygame runtime loop
GameScreen         — экранный оркестратор
GameController     — правила и логическое состояние
GroupStore         — долгоживущие configured groups
Frame              — экранные зоны и локальные контейнеры
Group              — пассивный визуальный кирпич
Activity           — долгоживущий визуальный режим
Action             — короткое конечное визуальное действие
GuiManifest        — публичный язык визуального слоя
```

Главная проблема текущего кода не в том, что архитектуры нет.

Проблема в другом:

```text
Код местами обходит собственный архитектурный контракт.
```

Наиболее частые нарушения:

```text
Activity берёт на себя обязанности GameScreen.
Activity обращается с visual Group как с игровой сущностью.
Код напрямую мутирует внутренности Frame, Screen и Group.
Координатные системы используются не всегда явно.
Animation существует рядом с Action без ясного разделения ролей.
Некоторые Activity запускают и завершают другие Activity без явного ownership.
```

---

# 2. Критические отклонения кода от документации

## 2.1. Activity местами берёт на себя роль GameScreen

### Что говорит документация

`GameScreen` — экранный оркестратор. Он владеет экранными зонами, активным набором group ID, маршрутизирует ввод, запускает визуальные процессы и управляет жизненным циклом активных `Activity` / `Action`.

`Activity` — долгоживущий визуальный режим. Она не должна становиться экранным оркестратором.

### Что видно в коде

В некоторых Activity-классах логика выходит за рамки локального визуального режима.

Особенно заметный пример — `PlayAreaSlotsActivity`, которая:

```text
создаёт slot frames;
создаёт slot activities;
добавляет activity в screen;
удаляет activity из screen.active_activities;
удаляет frame из screen.screen_frames;
мутирует play_area_frame.child_frames;
регистрирует activity в screen.hand_activities;
считает layout;
применяет fixtures.
```

Это уже не только визуальный режим. Это частичный экранный оркестратор.

### Почему это критично

Если Activity начинает управлять registry экрана, то `GameScreen` перестаёт быть единственным авторитетом жизненного цикла экранных объектов.

Возникает риск:

```text
один объект уже удалён из одного registry,
но остался в другом;
Activity завершена, но frame ещё существует;
frame удалён, но activity продолжает обновляться;
prototype activity выпала из slot_activities, но осталась активной.
```

### Как исправлять

Перенести ответственность:

```text
GameScreen:
    создаёт и удаляет Frame;
    создаёт и регистрирует Activity;
    добавляет/удаляет Activity из active_activities;
    владеет screen-level registry.

PlayAreaSlotsActivity:
    получает назначенные slot frames;
    рассчитывает layout;
    применяет позиции;
    может запустить Action, если это часть визуального режима.
```

Компромиссный вариант:

```text
PlayAreaSlotsActivity не мутирует screen напрямую,
а вызывает публичные методы GameScreen:
    create_slot_frame()
    remove_slot_frame()
    add_activity()
    remove_activity()
```

---

## 2.2. Activity использует visual Group как игровую сущность

### Что говорит документация

`GameController` принимает игровые решения.  
`GameScreen` превращает visual input в `ScreenInputEvent`.  
`ScreenInputEvent` описывает визуальный факт: group id, frame id, screen/local position.  
Контроллер решает, имеет ли этот факт игровой смысл.

### Что видно в коде

`CardSelectionActivity` работает примерно так:

```text
найти Group под курсором;
если double click — считать Group выбранной;
сохранить selected_group;
запустить player_turn_activity.
```

Это делает визуальную группу фактическим носителем игрового выбора.

### Почему это критично

`Group` — это визуальный объект.

Он может:

```text
быть пересоздан;
быть visual-only proxy;
не иметь стабильного отношения к игровой карте;
иметь id, удобный для GUI, но не для правил;
исчезнуть при layout rebuild;
быть частью hover-анимации, а не game state.
```

Если игровой сценарий зависит от `Group`, визуальный слой начинает протекать в игровую логику.

### Как исправлять

Правильный поток:

```text
pygame event
-> GameScreen.build_input_event()
-> GameScreen.hit_test()
-> ScreenInputEvent(group_id, frame_id, screen_pos, local_pos)
-> GameController.handle_input()
-> VisualCommand[]
-> GameScreen.dispatch_visual_command()
-> Activity / Action
```

Если `CardSelectionActivity` остаётся, её роль должна быть визуальной:

```text
поднять карту на hover;
подсветить видимую карту;
рассчитать visual hit zones;
показать feedback.
```

Но решение:

```text
можно ли выбрать карту;
какая карта выбрана;
что значит double click;
можно ли начать ход;
```

должно проходить через `GameController`.

---

## 2.3. Код напрямую мутирует внутренности Frame, Screen и Group

### Что говорит документация

Манифест требует:

```text
Любые изменения визуального состояния проходят через явные методы Group,
а не через прямое изменение внутренних словарей.
```

Также `GameScreen` и `Frame` должны быть владельцами своих registry и геометрии.

### Что видно в коде

В разных файлах встречаются такие действия:

```python
self.frame.group_origins[group.id] = group.local_rect.topleft
self.frame.group_origins.pop(group.id, None)

self.screen.screen_frames.pop(frame_id, None)
self.play_area_frame.child_frames.pop(frame_id, None)
self.screen.active_activities.remove(activity)

group.layers[0].frames = [rotated_surface]
group.layers[0].position = (0, 0)

self.hand_activity.card_resource_provider = self.get_card_resource_key
self.hand_activity.card_layer_name = "card"
self.hand_activity.card_count = len(self.card_resource_keys)
```

### Почему это критично

Прямая мутация обходит:

```text
dirty flags;
layout cache;
screen/local projection cache;
z-order;
hit-test cache;
activity cleanup;
animation cleanup;
debug overlays;
parent/child synchronization;
валидацию.
```

Объект-владелец может не узнать, что его состояние изменилось.

### Как исправлять

Добавить публичные методы:

```python
Frame.add_group(group_id)
Frame.remove_group(group_id)
Frame.set_group_origin(group_id, position)

Screen.create_frame(...)
Screen.remove_frame(frame_id)
Screen.add_activity(activity)
Screen.remove_activity(activity)

Group.replace_layer_frames(layer_name, frames)
Group.set_layer_position(layer_name, position)
Group.set_layer_frame_index(layer_name, index)

HandActivity.configure_card_resources(provider, layer_name, card_count)
HandActivity.rebuild_visual_groups()
```

Принцип:

```text
Внешний код не меняет внутреннее поле.
Внешний код просит владельца выполнить действие.
```

---

## 2.4. Координатные системы используются не всегда явно

### Что говорит документация

Документация задаёт строгий coordinate contract:

```text
Screen coordinates
    Frame local coordinates
        nested Frame local coordinates
            Group local coordinates
                Layer local coordinates
```

`local_rect` хранится относительно parent.  
`rect` является screen-space projection.  
Screen-space geometry — runtime projection, не второй источник истины.  
Movement может интерполироваться в screen coordinates только как animation convenience, но финальная позиция должна быть разрешена обратно в local rect.

### Что видно в коде

Проблемные места:

```text
CardsSlotActivityDecorator:
    bounds может считаться через scaled local rect,
    а сдвиг группы делается через обычный local_rect.

PlayAreaSlotsActivity:
    fan_rect/frame.rect используются как будто оба screen-space,
    потом конвертируются через play_area_frame.to_local(...).

MoveGroupAnimation:
    работает в screen coordinates,
    но нет явного финального resolution обратно в local rect.

BotHandActivity / PlayerHandActivity:
    scale, local scale, rotated surface, pivot, local_rect смешаны в одном pipeline.
```

### Почему это критично

Ошибки координат редко дают понятный crash.

Они проявляются так:

```text
карта чуть уехала;
debug rect не совпадает;
при scale всё ломается;
после resize всё съезжает;
hover работает не там, где видна карта;
после animation объект snap-ится назад.
```

### Как исправлять

Ввести строгие имена и API:

```python
calculate_fan_local_rect()
calculate_fan_screen_rect()
get_slot_content_local_rect()
get_slot_content_scaled_local_rect()
local_rect_to_screen_rect()
screen_rect_to_local_rect()
resolve_screen_position_to_local(parent_frame, screen_pos)
```

Запретить методы с неопределённой системой координат:

```python
calculate_fan_rect()
get_slot_content_rect()
get_group_slot_rect()
```

Или дописать в docstring точный coordinate space.

---

## 2.5. Activity запускает и завершает вложенные Activity без явного ownership

### Что говорит документация

`GameScreen` хранит список активных Activity и удаляет завершённые Activity.  
Activity может быть долгоживущей и жить весь игровой сеанс.

### Что видно в коде

Некоторые классы делают:

```python
self.hand_activity.start()
self.hand_activity.finish()

self.play_area_slots_activity.start()
self.play_area_slots_activity.finish()
```

Но неясно, вложенная Activity принадлежит текущей Activity или является долгоживущим визуальным сервисом экрана.

### Почему это критично

Например:

```text
CardSelectionActivity.finish()
    может завершить hand_activity,
    хотя рука должна остаться на экране.

PlayerTurnActivity.finish()
    может завершить play_area_slots_activity,
    хотя слоты стола должны жить дольше одного хода.
```

### Как исправлять

Добавить ownership contract:

```python
def __init__(self, hand_activity, owns_hand_activity=False):
    self.hand_activity = hand_activity
    self.owns_hand_activity = owns_hand_activity
```

И правило:

```text
Если Activity получила другую Activity извне,
она не завершает её без явного owns_* = True.
```

Более архитектурно чистый вариант:

```text
GameScreen создаёт и владеет долгоживущими Activity.
Activity может создавать и владеть только своими короткими Action.
```

---

## 2.6. Animation и Action не разведены

### Что говорит документация

`Action` — короткое конечное визуальное действие.  
`Activity` может запускать Action.  
`Group` остаётся пассивным объектом.

### Что видно в коде

Есть классы:

```text
Animation
CardSelectionAnimation
MoveGroupAnimation
```

Они напрямую мутируют `Group`:

```python
group.set_local_position(...)
group.set_position(...)
group.set_scale_factor(...)
```

Но архитектурно неясно:

```text
Animation — это Action?
Animation — низкоуровневый primitive?
Кто владеет animation?
Кто отменяет animation?
Что делать при конфликте двух animation?
```

### Почему это критично

Если layout и animation одновременно пишут в position/scale, появятся:

```text
дрожание;
snap-back;
конфликт hover и move;
устаревшие ссылки на удалённые groups;
непредсказуемый порядок применения.
```

### Как исправлять

Документально и кодово развести роли:

```text
Animation:
    низкоуровневый интерполятор progress -> visual property.

Action:
    архитектурная единица короткого конечного шага,
    владеет Animation,
    знает target group,
    имеет finish/cancel,
    сообщает владельцу о завершении.
```

Пример:

```text
MoveGroupAction
    uses MoveGroupAnimation

CardHoverAction
    uses CardSelectionAnimation

ScaleGroupAction
    uses ScaleAnimation
```

Activity должна запускать Action, а не разрастаться собственными animation-dict без общего lifecycle.

---

## 2.7. Generated groups разрешены, но их draw/lifecycle contract не до конца соблюдён

### Что говорит документация

Generated visual groups принадлежат Activity.  
Они являются экранными представлениями данных контроллера.  
Activity отвечает за их ID, размещение во Frame, обновление и удаление.

### Что видно в коде

`BotHandActivity` и производные классы действительно создают visual-only groups, что соответствует документации.

Но есть риски:

```text
Activity добавляет group во Frame;
Activity сама же рисует group;
Frame/GameScreen тоже могут рисовать group;
Activity напрямую меняет frame.group_origins;
удаление group может быть неполным, если есть registry вне Frame.
```

### Почему это критично

Две системы могут одновременно считать себя владельцами отрисовки и жизненного цикла.

### Как исправлять

Зафиксировать правило:

```text
Если generated group добавлен во Frame,
его рисует Frame/GameScreen.

Activity:
    создаёт group;
    добавляет group во Frame через публичный API;
    обновляет local_rect через публичный API;
    удаляет group через публичный API;
    не вызывает group.draw(screen) сама.
```

Если нужен special draw order, он должен задаваться через API Frame/GameScreen, а не ручным draw внутри Activity.

---

# 3. Пути совершенствования текущей архитектуры

## 3.1. Не вводить лишние глобальные менеджеры

Первое важное уточнение: манифест требует плоскую структуру.

Поэтому не стоит автоматически добавлять:

```text
AnimationManager
ActivityManager
ScreenManager
LayoutManager
```

как новые глобальные центры власти.

Лучше:

```text
GameScreen остаётся экранным оркестратором.
Frame владеет локальной геометрией зоны.
Activity владеет своим визуальным режимом.
Action владеет коротким конечным шагом.
```

Но внутри `GameScreen` допустимы простые коллекции:

```python
self.active_group_ids
self.active_activities
self.active_actions
self.frames
```

Это не отдельная менеджеризация, а реализация роли `GameScreen`.

---

## 3.2. Перевести screen-level создание объектов в GameScreen

### Текущее состояние

Некоторые Activity сами создают/удаляют Frames и регистрируют Activity.

### Целевое состояние

```text
GameScreen:
    create_frame()
    remove_frame()
    add_activity()
    remove_activity()
    add_action()
    remove_action()
    dispatch_visual_command()

Activity:
    request/receive assigned frame
    manage visual-only groups внутри assigned frame
    start actions for local visual behavior
```

### Практический шаг

Вынести из `PlayAreaSlotsActivity`:

```text
ensure_slot_frames()
ensure_slot_activities()
remove_slot_frame()
remove_slot_activity()
```

на уровень `GameScreen` или Screen API.

В самой Activity оставить:

```text
calculate slot layout
apply positions to slot frames
apply visual fixture/config to already existing slot activities,
если это действительно её ответственность.
```

---

## 3.3. Ввести публичный API для Frame и Group

### Нужно добавить в Frame

```python
add_group_id(group_id)
remove_group_id(group_id)
set_group_origin(group_id, position)
place_group(group, local_rect)
remove_child_frame(frame_id)
add_child_frame(frame)
```

Если некоторые методы уже есть, важно перестать обходить их прямым доступом к словарям.

### Нужно добавить в Group

```python
set_local_rect(rect)
set_local_position(x, y)
set_position_screen(x, y)
set_scale_factor(scale)
replace_layer_frames(layer_name, frames)
set_layer_resource(layer_name, resource_key)
set_layer_frame_index(layer_name, index)
get_layer(layer_name)
```

### Результат

Activity перестанут знать внутреннее устройство:

```text
group.layers[0]
frame.group_origins
screen.screen_frames
```

---

## 3.4. Сделать coordinate-space явным в именах

### Проблемные текущие имена

```python
calculate_fan_rect()
get_slot_content_rect()
get_group_slot_rect()
set_position()
```

### Улучшенные варианты

```python
calculate_fan_screen_rect()
calculate_fan_local_rect()

get_slot_content_local_rect()
get_slot_content_scaled_local_rect()

get_group_slot_local_rect()
get_group_slot_screen_rect()

set_screen_position()
set_local_position()
```

### Правило

Каждый метод, который принимает или возвращает координаты, должен отвечать на вопрос:

```text
Это screen-space или parent-local?
Это scaled или unscaled?
```

---

## 3.5. Упорядочить Action/Animation

### Целевая структура

```text
Action:
    start()
    update(dt)
    finish()
    cancel()
    is_finished()

Animation:
    interpolate progress
    не принимает игровых решений
    не живёт отдельно в GameScreen
```

### Примеры

```text
MoveGroupAction:
    владеет MoveGroupAnimation,
    знает group_id,
    знает frame-owner,
    в конце resolve screen position -> local rect.

CardHoverAction:
    владеет scale/lift animation,
    может быть отменён при уходе hover.

FlipCardAction:
    меняет layer frame index.
```

### Важное правило

```text
Activity может запускать Action.
Activity не должна становиться складом разнородных animation без cancel/finish semantics.
```

---

## 3.6. Перестроить выбор карты вокруг GameController

### Текущий риск

```text
CardSelectionActivity сама считает double click игровым выбором.
```

### Целевой поток

```text
1. GameScreen получает pygame event.
2. GameScreen строит ScreenInputEvent.
3. GameController.handle_input(event) решает, что делать.
4. Controller возвращает VisualCommand.
5. GameScreen запускает Activity/Action.
```

### Роль CardSelectionActivity

```text
hover feedback;
visual affordance;
подсветка;
lift/scale;
возможно — подсказка видимой зоны.
```

Но не:

```text
решение о ходе;
выбор игровой карты;
старт player turn как игрового сценария.
```

---

## 3.7. Стабилизировать transform pipeline карт

### Проблема

Сейчас scale, rotate, pivot и local_rect смешаны.

### Целевой pipeline

```text
base surface
-> scale surface
-> rotate scaled surface
-> calculate pivot on actual rotated surface
-> set local rect in parent-frame local coordinates
-> render through normal Group draw pipeline
```

### Важное решение

Выбрать один источник масштаба:

```text
либо surface scale;
либо group scale;
но не смесь обоих без строгого контракта.
```

С учётом документации, где scale является частью projection, лучше осторожно:

```text
local rect остаётся unscaled;
scale применяется при projection/draw;
pivot должен считаться в той же модели, которую использует draw.
```

Если это слишком сложно для rotated cards, можно для generated card groups использовать уже pre-scaled rotated surfaces и `group.scale_factor = 1.0`.

Главное — один ясный контракт.

---

## 3.8. Уточнить RenderEngine без расширения его ответственности

### Разрешённые улучшения

`RenderEngine` может получить:

```text
try/finally pygame.quit()
target_fps
max_dt
screen lifecycle start/finish
runtime context для screen_factory
```

### Чего не делать

Не превращать `RenderEngine` в:

```text
GameScreen manager
Activity manager
Controller coordinator
input semantic layer
```

Эти роли принадлежат `GameScreen` / `GameController`.

---

# 4. Приоритетный план исправлений

## Этап 1. Закрепить архитектурные границы

### Цель

Остановить рост нарушений контракта.

### Действия

1. Запретить новые прямые мутации:
   ```text
   screen.screen_frames
   screen.active_activities
   frame.child_frames
   frame.group_origins
   group.layers[0]
   ```

2. Добавить публичные методы в `Frame`, `Screen`, `Group`.

3. Зафиксировать правило:
   ```text
   Activity не создаёт и не удаляет Frame напрямую.
   Activity не регистрирует другие Activity напрямую.
   ```

4. Добавить ownership-флаг для Activity, которые оборачивают другие Activity.

---

## Этап 2. Привести input flow к документации

### Цель

Убрать игровую семантику из Activity.

### Действия

1. Перенести double-click decision в `GameController`.
2. `CardSelectionActivity` оставить только для visual hover/selection feedback.
3. Ввести mapping:
   ```text
   group_id -> card_id / hand_index
   ```
   на уровне `GameScreen` или view model.
4. `PlayerTurnActivity` запускать через `VisualCommand`, а не напрямую из selection activity.

---

## Этап 3. Разделить Action и Animation

### Цель

Сделать короткие визуальные шаги частью архитектуры, а не случайными animation-классами.

### Действия

1. Оставить `Animation` как low-level primitive.
2. Создать `Action`-обёртки:
   ```text
   MoveGroupAction
   CardHoverAction
   ScaleGroupAction
   ```
3. Добавить `cancel()`.
4. Добавить правило one-shot для animation/action instances.
5. Screen-coordinate move в конце должен делать:
   ```text
   screen position -> parent frame local rect
   ```

---

## Этап 4. Стабилизировать координаты и layout

### Цель

Убрать неявные local/screen/scaled смешения.

### Действия

1. Переименовать неоднозначные методы:
   ```text
   calculate_fan_rect -> calculate_fan_screen_rect/local_rect
   get_slot_content_rect -> get_slot_content_local_rect/scaled_rect
   ```
2. Добавить docstring coordinate-space для каждого geometry метода.
3. Убрать смешение `get_scaled_local_rect()` и `local_rect`.
4. Ввести `layout_dirty` или layout signature для Activity, где layout может устаревать.

---

## Этап 5. Исправить generated groups pipeline

### Цель

Сделать visual-only groups полностью соответствующими манифесту.

### Действия

1. Activity создаёт generated groups.
2. Activity добавляет их во Frame через публичный API.
3. Frame/GameScreen рисует registered groups.
4. Activity не вызывает `group.draw()` для registered groups.
5. Activity удаляет generated groups через публичный API.
6. Generated group не становится игровой сущностью.

---

## Этап 6. Почистить технический долг

### Действия

1. Добавить type hints / Protocol для:
   ```text
   Group-like
   Frame-like
   Activity-like
   Action-like
   GameScreen-like
   ```
2. Валидировать fixture values.
3. Убрать неиспользуемые параметры:
   ```text
   columns
   get_center_out_offset
   scale_surface
   ```
   или начать их использовать.
4. Разделить debug/runtime:
   ```text
   cards_from_manifest -> debug provider
   runtime cards -> controller/view model
   ```

---

# 5. Что стоит уточнить в документации

## 5.1. Ownership вложенных Activity

Добавить правило:

```text
Если Activity получила другую Activity извне, она не завершает её,
если явно не объявлено owns_child_activity=True.
```

Или альтернативное правило:

```text
Composite Activity владеет всеми child Activity, которые сама создаёт.
Полученные извне Activity считаются screen-owned.
```

---

## 5.2. Activity и Frame

Добавить правило:

```text
Activity может создавать visual-only Group.
Activity не создаёт и не удаляет Frame напрямую.
Создание/удаление Frame выполняет GameScreen через публичный API.
```

---

## 5.3. Draw ownership generated groups

Добавить правило:

```text
Если generated group добавлен во Frame,
он рисуется обычным draw pipeline Frame/GameScreen.

Если Activity рисует group сама,
она не регистрирует этот group во Frame draw pipeline.
```

Рекомендуемый вариант:

```text
Frame/GameScreen рисует всё, что находится во Frame.
Activity только обновляет состояние.
```

---

## 5.4. Action vs Animation

Добавить определение:

```text
Animation — низкоуровневый interpolation primitive.
Action — архитектурный короткий конечный визуальный шаг.
Action может использовать одну или несколько Animation.
Activity и GameScreen оперируют Action, а не голыми Animation.
```

---

## 5.5. Screen-space movement

Уточнить обязательное правило:

```text
Screen-space movement разрешён только как временная animation convenience.
После завершения движение обязано быть преобразовано обратно
в local_rect относительно текущего или нового parent Frame.
```

---

# 6. Таблица критических отклонений

| Отклонение | Нарушенный принцип | Где проявляется | Приоритет |
|---|---|---|---|
| Activity создаёт/удаляет Frame и регистрирует Activity | GameScreen — экранный оркестратор | `PlayAreaSlotsActivity` | Критический |
| Activity выбирает visual Group как игровую карту | GameController решает game meaning | `CardSelectionActivity`, `PlayerTurnActivity` | Критический |
| Прямая мутация внутренних структур | Слойный API вместо скрытой магии | `Frame`, `Screen`, `Group`, decorators | Критический |
| Неявные local/screen/scaled координаты | Локальные координаты контейнеров | slots, hands, animations | Критический |
| Вложенные Activity завершаются без ownership | GameScreen владеет active Activity lifecycle | decorators, turn/selection activities | Высокий |
| Animation не оформлена как Action | Action — короткий конечный шаг | animation classes, hover | Высокий |
| Generated groups могут рисоваться дважды | GameScreen/Frame draw pipeline должен быть единственным | hand activities | Высокий |
| Screen-space move не гарантирует local resolution | Screen-space geometry не source of truth | move animations/actions | Высокий |
| Fixture используется как мешок параметров | Слабый публичный контракт | многие Activity | Средний |
| Debug path смешан с runtime path | Controller должен давать реальные данные | visible card decorator | Средний |

---

# 7. Целевое состояние после улучшений

После исправлений архитектура должна выглядеть так:

```text
RenderEngine
    только pygame runtime loop

GameScreen
    владеет frames
    владеет active group ids
    владеет active activities/actions
    строит ScreenInputEvent
    вызывает GameController
    исполняет VisualCommand

GameController
    знает правила
    знает card_id / zones / state
    не знает Group / pygame

GroupStore
    хранит configured long-lived groups

Frame
    локальная геометрия
    group ids
    local-to-screen projection

Group
    пассивный visual object
    API для позиции, scale, layer frames

Activity
    долгоживущий visual mode
    может владеть generated visual-only groups
    может запускать short Actions
    не решает game rules

Action
    короткий visual step
    может использовать Animation
    имеет finish/cancel
```

---

# 8. Итоговая формулировка

Текущая документация проекта уже достаточно сильная. Её не нужно радикально переписывать.

Главная задача — привести код к уже написанному контракту.

Самые важные направления совершенствования:

```text
1. Вернуть GameScreen роль единственного экранного оркестратора.
2. Не использовать Group как игровую сущность.
3. Запретить прямую мутацию внутренних структур.
4. Сделать coordinate-space явным во всех geometry API.
5. Перевести короткие Animation в архитектурные Action.
6. Уточнить ownership вложенных Activity.
7. Сделать generated groups частью обычного Frame/GameScreen draw pipeline.
```

Если сделать эти шаги сейчас, проект сохранит простую плоскую архитектуру без лишних менеджеров, но станет намного устойчивее к росту: появлению реального `GameController`, ходов игроков, выбора карт, drag/drop, flip-анимаций и controller-driven визуальных команд.
