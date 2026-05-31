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
    active_zone.py
    game_screen.py

gui_actor/
    gui_actor.py
    gui_actor_store.py

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
- создает пустой `GuiActorStore`;
- фиксирует `SCREEN_SIZE` и `WINDOW_TITLE`;
- не запускает `RenderEngine`, потому что актуальные игровые экраны еще не
  собраны.

## base.py

Файл контрактов.

Содержит:

- `BaseGameScreen`;
- `BaseGameController`;
- `BaseActivity`;
- `BaseActiveZone`;
- `BaseGuiActor`.

В этом файле не должно быть игровой логики, загрузки ресурсов или отрисовки.

## core/game_state.py

Черновые структуры fixture-состояния.

Содержит:

- `CardState`;
- `GameState`.

`GameState` хранит:

- `cards`: описание карт по `card_id`;
- `zones`: порядок `card_id` внутри логических зон.

## core/game_controller.py

Черновой контроллер без правил игры.

Сейчас он:

- хранит `GameState`;
- принимает fixture через `load_fixture(state)`;
- возвращает snapshot через `get_state()`;
- сохраняет клики по actor ID в `clicked_actor_ids`.

Он не импортирует `pygame`, `GuiActor` или `ResourceManager`.

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

`ResourceManager` не знает про `GuiActor`, `GameScreen`, `Activity` и правила
игры. Для actor-ов основной метод получения графики - `get_frames(key)`: статичный
PNG возвращается как список из одного `Surface`, spritesheet - как список кадров.

## gui_actor/gui_actor.py

Пассивный визуальный объект.

`GuiActor`:

- имеет `id`;
- имеет `rect`;
- имеет `hit_rect`;
- имеет `scale_factor`;
- хранит список слоев в порядке отрисовки;
- каждый слой хранит только `name`, `frames`, `current_frame_index`;
- рисует текущий кадр каждого слоя из точки `actor.rect.topleft`;
- умеет собрать actor через `create_actor()` из описаний слоев;
- получает готовые кадры только через `ResourceManager.get_frames()`;
- не читает PNG напрямую и не хранит собственный кэш ресурсов;
- не проигрывает анимацию сам.

У слоя сознательно нет `offset`, `visible` и `alpha`. Смена позиции и масштаба
идет на уровне всего actor-а. Смена анимационного состояния идет через
`set_layer_frame(layer_name, frame_index)`.

## gui_actor/gui_actor_store.py

Единый контейнер созданных `GuiActor`.

Хранит actor-ы по стабильному ID и предоставляет:

- `add(actor)`;
- `get(actor_id)`;
- `has(actor_id)`;
- `remove(actor_id)`;
- `all_ids()`.

Store не знает правил игры, экранных зон и активностей.

## game_screen/game_screen.py

Базовая экранная сцена.

`GameScreen` хранит:

- `actor_store`;
- `game_controller`;
- `active_actor_ids`;
- `active_activities`;
- `screen_zones`.

Он не является складом всех actor-ов. Он активирует нужные actor ID и берет
сами объекты из `GuiActorStore`.

## game_screen/active_zone.py

Экранный контейнер для actor-ов.

`ActiveZone`:

- хранит `zone_id`;
- хранит `rect`;
- хранит `hit_rect`;
- хранит `actor_ids`;
- умеет применить простой layout к actor-ам через `GuiActorStore` и
  `actor.set_position(...)`.

Это не логическая зона правил игры. Это экранная зона размещения.

## activities/base_activity.py

Базовая визуальная активность.

`Activity`:

- хранит `actor_ids`;
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
- формировать tuple-слой для настройки `GuiActor.create_actor()`.

## Ownership

```text
GameController -> logical state fixture
GuiActorStore  -> all GuiActor instances
GameScreen     -> active actor IDs, activities, screen zones
ActiveZone     -> screen rect/hit_rect and layout for actor IDs
Activity       -> temporary visual process
GuiActor       -> passive drawable state
ResourceManager -> low-level resource cache
```

## Ближайшая точка развития

Сейчас проект готов к следующему шагу: созданию первых конкретных Activity и
позднее сборке первого актуального игрового экрана.
