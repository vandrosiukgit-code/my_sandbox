# Архитектура The Fool's Reef

Краткая справка по текущему состоянию кода. Архитектурный манифест остается
главным документом: `docs/architectural_manifesto_v6.2.md`.

## Текущий статус

Проект находится в стадии архитектурного рефакторинга. Игровая логика,
полноценные игровые экраны и переключение экранов еще не собраны.

`main.py` сейчас является черновым composition root: он создает минимальный
контекст приложения, но пока не запускает `RenderEngine`.

## Структура модулей

```text
main.py
base.py

core/
    game_controller.py
    game_state.py
    render_engine.py
    resource.py

game_screen/
    frame.py
    game_screen.py

group/
    group.py
    group_store.py

groups_store/
    table_group.py

activities/
    base_activity.py

tools/
    resource_picker.py

assets/
docs/
```

## main.py

Черновая точка входа.

Сейчас делает только базовую сборку контекста:

- создает `GameController` с fixture-состоянием;
- создает `GroupStore` с подключенным `ResourceManager`;
- фиксирует `SCREEN_SIZE` и `WINDOW_TITLE`;
- не запускает `RenderEngine`, потому что актуальные игровые экраны еще не
  собраны.

## base.py

Файл контрактов.

Содержит:

- `BaseGameScreen`;
- `BaseGameController`;
- `BaseActivity`;
- `BaseFrame`;
- `BaseGroup`.

В этом файле не должно быть игровой логики, загрузки ресурсов или отрисовки.

## core/game_state.py

Черновые структуры fixture-состояния.

Содержит:

- `CardState`;
- `GameState`.

`GameState` хранит:

- `cards`: описание карт по `card_id`;
- `frames`: порядок `card_id` внутри логических зон.

## core/game_controller.py

Черновой контроллер без правил игры.

Сейчас он:

- хранит `GameState`;
- принимает fixture через `load_fixture(state)`;
- возвращает snapshot через `get_state()`;
- сохраняет клики по group ID в `clicked_group_ids`.

Он не импортирует `pygame`, `Group` или `ResourceManager`.

## core/render_engine.py

Pygame runtime:

- создает окно;
- держит FPS;
- принимает события;
- вызывает `handle_event/update/draw` активного экрана;
- обновляет display.

На текущем этапе `main.py` его еще не запускает.

## core/resource.py

Низкоуровневый склад графических ресурсов.

Главные режимы:

- `build_index(assets_dir)` — metadata-only индекс без `pygame.Surface`;
- `build_runtime_cache(assets_dir)` — индекс плюс загрузка `Surface/frames`;
- `load_surfaces_from_index()` — догрузка поверхностей после уже построенного
  index.

`ResourceManager` не знает про `Group`, `GameScreen`, `Activity` и правила
игры. Для group-ов основной метод получения графики - `get_frames(key)`: статичный
PNG возвращается как список из одного `Surface`, spritesheet - как список кадров.

## group/group.py

Пассивный визуальный объект.

`Group`:

- имеет `id`;
- имеет `rect`;
- имеет `hit_rect`;
- имеет `scale_factor`;
- хранит список слоев в порядке отрисовки;
- каждый слой хранит только `name`, `frames`, `current_frame_index`;
- рисует текущий кадр каждого слоя из точки `group.rect.topleft`;
- умеет собрать group через `create_group()` из описаний слоев;
- получает готовые кадры только через `ResourceManager.get_frames()`;
- не читает PNG напрямую и не хранит собственный кэш ресурсов;
- не проигрывает анимацию сам.

У слоя сознательно нет `offset`, `visible` и `alpha`. Смена позиции и масштаба
идет на уровне всего group-а. Смена анимационного состояния идет через
`set_layer_frame(layer_name, frame_index)`.

## group/group_store.py

Единый контейнер созданных `Group`.

Хранит group-ы по стабильному ID и предоставляет:

- `build()`;
- `add_many(groups)`;
- `add(group)`;
- `get(group_id)`;
- `has(group_id)`;
- `remove(group_id)`;
- `all_ids()`.

Store не знает правил игры, экранных зон и активностей. При этом он является
точкой массовой сборки графических объектов: метод `build()` вызывает
builder-функции из `groups_store/` и складывает созданные group-ы в общий
словарь.

Конкретные group-модули подключаются в `GroupStore` как пути к модулям и
импортируются лениво во время `build()`. Это защищает базовый пакет `group`
от жесткой связи с конкретными объектами игры при обычном импорте.

`build()` нужно вызывать только после того, как `ResourceManager` собрал
runtime-кэш с pygame Surface/frames.

## groups_store/table_group.py

Модуль конкретного Group-а.

Содержит функцию:

- `create(resource_manager)`.

Функция описывает слои `table_group`, получает кадры через переданный
`resource_manager` и возвращает готовый `Group`. Она не импортирует `main.py`
и не мутирует `GroupStore` напрямую.

## game_screen/game_screen.py

Базовая экранная сцена.

`GameScreen` хранит:

- `group_store`;
- `game_controller`;
- `active_group_ids`;
- `active_activities`;
- `screen_frames`.

Он не является складом всех group-ов. Он активирует нужные group ID и берет
сами объекты из `GroupStore`.

## game_screen/frame.py

Экранный контейнер для group-ов.

`Frame`:

- хранит `frame_id`;
- хранит `rect`;
- хранит `hit_rect`;
- хранит `group_ids`;
- умеет применить простой layout к group-ам через `GroupStore` и
  `group.set_position(...)`.

Это не логическая зона правил игры. Это экранная зона размещения.

## activities/base_activity.py

Базовая визуальная активность.

`Activity`:

- хранит `group_ids`;
- хранит `duration`;
- считает `elapsed`;
- имеет `start()`;
- имеет `update(dt)`;
- имеет `finish()`;
- имеет `is_finished()`;
- дает `get_progress()`.

Наследники будут использовать `apply(progress)` для движения, появления,
исчезновения и смены кадров.

## tools/resource_picker.py

Dev tool для просмотра ресурсов.

Работает через `ResourceManager.build_index()`, поэтому не требует
`pygame.display`.

Умеет:

- показать дерево `assets/`;
- искать ресурсы по key, имени файла, пути и типу;
- показывать preview;
- формировать tuple-слой для настройки `Group.create_group()`.

## Ownership

```text
GameController -> logical state fixture
GroupStore  -> all Group instances
groups_store/* -> concrete Group builders
GameScreen     -> active group IDs, activities, screen frames
Frame     -> screen rect/hit_rect and layout for group IDs
Activity       -> temporary visual process
Group       -> passive drawable state
ResourceManager -> low-level resource cache
```

## Ближайшая точка развития

Сейчас проект готов к следующему шагу: созданию первых конкретных Activity и
позднее сборке первого актуального игрового экрана.
## Visual input/action flow

Актуальная граница ввода и визуальной механики описана в
`docs/visual_input_flow.md`.

Коротко:

```text
pygame event
    -> GameScreen normalizes input
    -> Frame hit-test
    -> ScreenInputEvent
    -> GameController.handle_input()
    -> GameState update
    -> VisualCommand
    -> GameScreen dispatch
    -> Frame Action
    -> Animation
    -> Group
```

`GameScreen` не решает, является ли двойной клик ходом. Он только сообщает
`GameController`, что произошел `double_click` по `group_id` в `frame_id`.
Игровой смысл, проверка правил и изменение `GameState` остаются в
`GameController`.

`Frame` принадлежит экрану и владеет локальными визуальными `Action`.
`Action` владеет набором `Animation`. Оба слоя не знают правил игры.


