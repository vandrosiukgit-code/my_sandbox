# Backlog рефакторинга под манифест The Fool's Reef

Документ фиксирует порядок работ для приведения текущего кода к `architectural_manifesto_v6.2.md`.

## Цель

Привести проект к архитектуре:

```text
main.py
    -> RenderEngine
        -> active GameScreen
            -> GameController
            -> GuiActorStore
            -> Activity instances
            -> active actor IDs
```

Главная граница:

- `GameController` владеет правилами, состоянием игры и логическими зонами.
- `GuiActorStore` владеет созданными графическими объектами.
- `GameScreen` владеет экранными зонами, активными actor ID и визуальной оркестрацией.
- `Activity` владеет временным визуальным процессом.
- `GuiActor` остается пассивным визуальным объектом.

## P0. Стабилизация текущей базы

### 1. Исправить базовый `GameScreen` [done]

Файлы:

- `game_screen/game_screen.py`
- `game_screen/__init__.py`

Задачи:

- восстановить корректное имя класса `GameScreen`;
- убрать модель владения `self.actors = []` как основной механизм;
- подготовить поля под новую схему:
  - `active_actor_ids`;
  - `active_activities`;
  - `screen_zones`;
  - ссылка на `GuiActorStore`;
  - ссылка на `GameController`.

Критерий готовности:

- `GameScreen` импортируется без ошибок;
- базовые методы `handle_event/update/draw` существуют;
- экран больше не считается складом всех `GuiActor`.

### 2. Синхронизировать `base.py` с манифестом [done]

Файл:

- `base.py`

Задачи:

- добавить базовый контракт для `BaseActivity`;
- добавить базовый контракт или минимальный интерфейс для `BaseGameController`;
- расширить `BaseGuiActor`:
  - обязательный `id`;
  - обязательный `rect`;
  - обязательный `hit_rect`;
  - `scale_factor`;
  - минимальные методы слоя: `set_layer_frame`, `set_layer_frames`;
- убрать из базового контракта акцент на `send_animation_command`, потому что анимационная логика уходит в `Activity`.

Критерий готовности:

- контракты отражают манифест;
- новые классы пока могут быть минимальными, без сложной реализации.

## P1. Разделение графических объектов и экранов

### 3. Создать `GuiActorStore` [done]

Файлы:

- `gui_actor/gui_actor_store.py`
- `gui_actor/__init__.py`

Задачи:

- создать контейнер `GuiActorStore`;
- хранить акторы по стабильному ID;
- предоставить методы:
  - `add(actor)`;
  - `get(actor_id)`;
  - `has(actor_id)`;
  - `remove(actor_id)`;
  - `all_ids()`;
- на первом этапе создавать акторы вручную через фабричные методы;
- не размещать акторы на экране внутри store.

Критерий готовности:

- `GameScreen` может получить actor по ID;
- `GuiActorStore` не знает правил игры, экранных зон и активностей.

### 4. Переделать `GuiActor` в пассивный визуальный объект [done]

Файл:

- `gui_actor/gui_actor.py`

Задачи:

- убрать прямой импорт и вызовы `ResourceManager`;
- принимать готовые `Surface` и кадры через конструктор;
- добавить `actor_id`;
- добавить `rect`;
- добавить `hit_rect`;
- хранить слои как явные объекты или структурированные словари;
- оставить `update(dt)` минимальным или пустым;
- перенести проигрывание кадров из `GuiActor.update()` в будущие `Activity`;
- добавить слойный API:
  - `set_position(x, y)`;
  - `set_hit_rect(rect)`;
  - `set_scale_factor(scale_factor)`;
  - `set_layer_frame(layer_name, frame_index)`;
  - `set_layer_frames(layer_name, frames)`;

Критерий готовности:

- `GuiActor` не читает файлы напрямую и получает Surface/frames только через `ResourceManager`;
- `GuiActor` ничего не решает про анимацию;
- `draw(screen)` только рисует текущие состояния слоев.

### 5. Перенести сборку графических объектов в `GuiActor` [done]

Возможные файлы:

- `gui_actor/gui_actor.py`
- или `gui_actor/builders.py`

Задачи:

- вынести сборку конкретных акторов из `GameScreen`;
- получать готовые ресурсы от `ResourceManager`;
- создавать:
  - акторы карт;
  - акторы кнопок;
  - акторы аватаров;
  - акторы фона/стола;
- наполнять `GuiActorStore` при старте игры.

Критерий готовности:

- `GameScreen` не содержит большого кода создания каждого графического объекта;
- все долгоживущие графические объекты создаются в одном понятном месте.

## P2. Игровая логика и события

### 6. Создать `GameController` [draft]

Файлы:

- `core/game_controller.py`

Задачи:

- создать модель игрового состояния;
- описать логические зоны:
  - `deck`;
  - `bottom_hand`;
  - `top_hand`;
  - `battle_table`;
  - `discard`;
- создать минимальную модель карты:
  - `card_id`;
  - `rank`;
  - `suit`;
  - `zone`;
- добавить методы:
  - `start_game()`;
  - `load_fixture(state)`;
  - `get_state()`;
  - `on_actor_clicked(actor_id)`;

Критерий готовности:

- контроллер может сформировать начальное состояние игры;
- контроллер может отдать fixture snapshot через `get_state()`;
- контроллер не импортирует `pygame`, `GuiActor`, `ResourceManager`.

### 7. Ввести визуальные запросы от логики к экрану [deferred]

Файлы:

- пока не создаются;

Задачи:

- отложено до появления настоящей игровой логики;
- на текущем этапе `GameScreen` работает напрямую с `GameState` fixture;
- `GameController` предоставляет `get_state()`;
- экран читает логические зоны из snapshot и сам активирует нужные actor ID.

Критерий готовности:

- фикстурное состояние можно прочитать через `GameController.get_state()`;
- `GameController` по-прежнему не импортирует `pygame`, `GuiActor`, `ResourceManager`.

## P3. Экранные зоны и активные actor ID

### 8. Описать ActiveZone

Файлы:

- `base.py`
- `game_screen/active_zone.py`
- `game_screen/__init__.py`

Задачи:

- создать контракт `BaseActiveZone`;
- создать заготовку `ActiveZone`;
- зона хранит `zone_id`, `rect`, `hit_rect`, `actor_ids`;
- зона умеет применить простой layout к actor-ам через `GuiActorStore`.

Критерий готовности:

- `ActiveZone` может принять actor ID и расставить соответствующие GuiActor;
- логическая зона не смешивается с экранной зоной.

### 9. Собрать игровые экраны [deferred]

Файл:

- будущие файлы экранов в `screens/`

Задачи:

- `MainGameScreen` удален как артефакт предыдущих этапов;
- игровые экраны будут собираться позже отдельным этапом;
- принимать `GameController` и `GuiActorStore` через конструктор;
- хранить `active_actor_ids`, а не список actor-объектов;
- в `update(dt)`:
  - читать `GameState` fixture из контроллера;
  - активировать нужные actor ID;
  - запускать `Activity`;
  - обновлять активности;
- в `draw(screen)`:
  - рисовать фон;
  - рисовать активные actor ID в порядке экранных зон;
- в `handle_event(event)`:
  - проверять `hit_rect` активных акторов;
  - передавать найденный ID в `GameController`.

Критерий готовности:

- экран является текущей сценой, а не владельцем всех акторов;
- взаимодействие идет через ID.

## P4. Activity

### 10. Создать базовую систему `Activity` [done]

Файлы:

- `activities/__init__.py`
- `activities/base_activity.py`

Задачи:

- создать базовый класс с методами:
  - `start()`;
  - `update(dt)`;
  - `is_finished`;
  - `finish()`;
- активность получает ссылки на нужные `GuiActor`, но не знает правил игры.

Критерий готовности:

- `GameScreen` может хранить и обновлять список активностей;
- завершенные активности удаляются экраном.

### 11. Реализовать первые активности

Файлы:

- `activities/move_actor_activity.py`
- `activities/show_actor_activity.py`
- `activities/hide_actor_activity.py`
- возможно `activities/frame_animation_activity.py`

Задачи:

- `MoveActorActivity`: плавно перемещает actor между позициями;
- `ScaleActorActivity`: меняет масштаб actor-а во времени;
- `ActivateActorActivity`: добавляет actor ID в активный набор экрана;
- `DeactivateActorActivity`: убирает actor ID из активного набора экрана;
- `FrameAnimationActivity`: меняет текущий кадр слоя по времени.

Критерий готовности:

- появление, перемещение и удаление карты можно сделать без логики внутри `GuiActor`.

## P5. ResourceManager и ресурсы

### 12. Уточнить контракт `ResourceManager` [done]

Файл:

- `core/resource.py`

Задачи:

- оставить `ResourceManager` единственным низкоуровневым кэшем ресурсов;
- поддержать рекурсивную структуру `assets/`;
- отделить runtime-index от загрузки `Surface`;
- подготовить чтение PNG metadata как целевой путь;
- сохранить совместимость с текущими info-файлами до миграции.

Критерий готовности:

- `ResourceManager` остается единственным источником Surface/frames;
- `GuiActor.create_actor()` собирает слои из resource keys.

### 13. Обновить `resource_picker` [done]

Файл:

- `tools/resource_picker.py`

Задачи:

- убедиться, что дерево папок `assets/` работает;
- довести поиск до стабильного состояния;
- сделать tuple-слой, пригодный для `GuiActor.create_actor()`;
- не завязывать dev tool на `pygame.display`.

Критерий готовности:

- инструмент помогает выбрать resource keys для сборки акторов.

## P6. Точка входа и сборка приложения

### 14. Переписать `main.py` [draft]

Файл:

- `main.py`

Задачи:

- зафиксировать будущую схему инициализации `RenderEngine`;
- пока не запускать `RenderEngine`, потому что игровые экраны еще не собраны;
- позже построить `ResourceManager` после создания pygame display;
- создать `GuiActorStore`;
- создать `GameController`;
- создать стартовый игровой экран после отдельного этапа сборки screens;
- передать активный экран в `RenderEngine`.

Критерий готовности:

- черновая сборка приложения видна из `main.py`;
- зависимости передаются явно.

### 15. Подготовить основу для нескольких экранов [deferred]

Файлы:

- будущие файлы экранов в `screens/`

Задачи:

- пропущено на текущем этапе;
- роутер/переключение экранов будет проектироваться после сборки первого актуального игрового экрана;
- зафиксировать общий контракт переключения экранов;
- решить, кто выбирает активный экран:
  - `RenderEngine`;
  - или отдельный легкий `ScreenRouter`.

Критерий готовности:

- появление второго экрана не требует копировать общую механику GameScreen.

## P7. Документация и проверки

### 16. Обновить документацию [done]

Файлы:

- `docs/architecture.md`
- `docs/architectural_manifesto_v6.2.md`
- `docs/refactor_backlog.md`

Задачи:

- синхронизировать старую справку `architecture.md` с манифестом;
- архитектурный манифест не менять, он актуален;
- добавить схему запуска;
- добавить схему ownership:

```text
GameController -> logical state
GuiActorStore  -> all GuiActor instances
GameScreen     -> screen zones + active actor IDs
Activity       -> temporary visual process
GuiActor       -> passive drawable state
```

Критерий готовности:

- документация не противоречит коду.

### 17. Минимальные smoke-проверки [deferred]

Задачи:

- пропущено на текущем этапе;
- вернемся к smoke-проверкам после сборки первого актуального игрового экрана;
- импортировать основные модули;
- запустить игру до первого кадра;
- проверить, что стартовый игровой экран рисуется;
- проверить, что `GameController` может раздать карты;
- проверить, что `GameScreen` активирует actor ID по `GameState` fixture;
- проверить, что клик по `hit_rect` передает ID в контроллер.

Критерий готовности:

- есть понятная команда для проверки;
- основные сценарии не падают при запуске.

## Рекомендуемый порядок выполнения

1. P0: стабилизировать `GameScreen` и `base.py`.
2. P1: сделать `GuiActorStore` и пассивный `GuiActor`.
3. P2: добавить черновой `GameController` и fixture-состояние.
4. P3: подготовить ActiveZone и позже собрать игровые экраны.
5. P4: добавить первые `Activity`.
6. P5: подчистить ресурсный контур и `resource_picker`.
7. P6: собрать все через `main.py`.
8. P7: обновить документацию и smoke-проверки.
