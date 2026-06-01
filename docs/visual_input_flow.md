# Visual Input Flow

Этот документ фиксирует границу между игровой логикой и визуальной механикой
экрана.

## Главный принцип

`GameScreen` не решает правила игры. Он обрабатывает pygame-события только как
технический input: клик, двойной клик, кнопка мыши, позиция, actor под курсором,
активная зона.

`GameController` получает нормализованное событие, решает его игровой смысл,
меняет `GameState` и возвращает визуальные команды.

```text
pygame event
    -> GameScreen
    -> ActiveZone hit-test
    -> ScreenInputEvent
    -> GameController.handle_input(event)
    -> GameState update
    -> VisualCommand
    -> GameScreen.dispatch_visual_command(command)
    -> ActiveZone.add_action(action)
    -> Action.update(dt)
    -> Animation.update(dt)
    -> GuiActor visual state
```

## ScreenInputEvent

`ScreenInputEvent` находится в `game_screen/events.py`.

Он описывает не смысл игры, а только факт пользовательского ввода:

```text
type        click | double_click | ...
button      left | right | middle | ...
actor_id    GuiActor под курсором, если есть
zone_id     ActiveZone под курсором, если есть
screen_pos  координаты pygame-экрана
local_pos   координаты внутри ActiveZone
```

Пример: двойной клик ЛКМ по карте в руке игрока:

```text
type = double_click
button = left
actor_id = card_6_clubs
zone_id = bottom_hand
screen_pos = (430, 610)
local_pos = (120, 18)
```

`GameScreen` не говорит "игрок сделал ход". Он говорит только: "был двойной
клик ЛКМ по actor в зоне".

## GameController

`GameController.handle_input(event)` интерпретирует событие:

```text
если event.type == double_click
если event.button == left
если event.zone_id == bottom_hand
если event.actor_id является картой текущего игрока
если правила разрешают ход
тогда обновить GameState и вернуть VisualCommand
```

На текущем этапе метод существует как draft: он записывает input и возвращает
пустой список команд. Правила игры будут добавлены позже.

## VisualCommand

`VisualCommand` также находится в `game_screen/events.py`.

Это ответ контроллера экрану. Команда сообщает, какое визуальное действие нужно
запустить, но не содержит pygame-кода.

Пример будущей команды:

```text
type = play_card
actor_id = card_6_clubs
from_zone = bottom_hand
to_zone = battle_table
```

`GameScreen.dispatch_visual_command()` принимает команду и передает ее в
визуальную систему: выбирает зоны, создает `Action`, запускает его в зоне.

## ActiveZone

`ActiveZone` принадлежит `GameScreen`.

Зона:

- хранит `actor_ids`;
- размещает actor-ы в локальной системе координат;
- переводит `screen_pos` в `local_pos`;
- делает hit-test actor-ов внутри зоны;
- владеет активными `Action`;
- обновляет `Action` каждый кадр.

Важно: `ActiveZone` не решает правила игры. Она знает только экранную геометрию
и визуальные процессы внутри своей области.

## Action

`Action` находится в пакете `actions/`.

Action описывает один визуальный сценарий: ход карты, раздача, сброс,
перемещение набора карт. Action может состоять из нескольких Animation.

Action запускается только после того, как `GameController` уже разрешил
действие и вернул `VisualCommand`.

## Animation

`Animation` находится в пакете `animations/`.

Animation делает конкретное изменение во времени:

- перемещение actor;
- масштаб;
- смена кадра;
- появление или исчезновение;
- переворот карты.

Animation не знает о правилах игры, `GameState` и `GameController`.

## Ownership

```text
GameController -> rules, GameState, input interpretation, VisualCommand
GameScreen     -> pygame adapter, screen zones, command dispatch
ActiveZone     -> local layout, hit-test, zone-owned Action list
Action         -> visual scenario composed from animations
Animation      -> frame-by-frame visual state change
GuiActor       -> passive drawable object
```
