# Visual Input Flow

Этот документ фиксирует границу между игровой логикой и визуальной механикой
экрана.

## Главный принцип

`GameScreen` не решает правила игры. Он обрабатывает pygame-события только как
технический input: клик, двойной клик, кнопка мыши, позиция, group под курсором,
активная зона.

`GameController` получает нормализованное событие, решает его игровой смысл,
меняет `GameState` и возвращает визуальные команды.

```text
pygame event
    -> GameScreen
    -> Frame hit-test
    -> ScreenInputEvent
    -> GameController.handle_input(event)
    -> GameState update
    -> VisualCommand
    -> GameScreen.dispatch_visual_command(command)
    -> Frame.add_action(action)
    -> Action.update(dt)
    -> Animation.update(dt)
    -> Group visual state
```

## ScreenInputEvent

`ScreenInputEvent` находится в `game_screen/events.py`.

Он описывает не смысл игры, а только факт пользовательского ввода:

```text
type        click | double_click | ...
button      left | right | middle | ...
group_id    Group под курсором, если есть
frame_id     Frame под курсором, если есть
screen_pos  координаты pygame-экрана
local_pos   координаты внутри Frame
```

Пример: двойной клик ЛКМ по карте в руке игрока:

```text
type = double_click
button = left
group_id = card_6_clubs
frame_id = bottom_hand
screen_pos = (430, 610)
local_pos = (120, 18)
```

`GameScreen` не говорит "игрок сделал ход". Он говорит только: "был двойной
клик ЛКМ по group в зоне".

## GameController

`GameController.handle_input(event)` интерпретирует событие:

```text
если event.type == double_click
если event.button == left
если event.frame_id == bottom_hand
если event.group_id является картой текущего игрока
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
group_id = card_6_clubs
from_frame = bottom_hand
to_frame = battle_table
```

`GameScreen.dispatch_visual_command()` принимает команду и передает ее в
визуальную систему: выбирает зоны, создает `Action`, запускает его в зоне.

## Frame

`Frame` принадлежит `GameScreen`.

Зона:

- хранит `group_ids`;
- размещает group-ы в локальной системе координат;
- переводит `screen_pos` в `local_pos`;
- делает hit-test group-ов внутри зоны;
- владеет активными `Action`;
- обновляет `Action` каждый кадр.

Важно: `Frame` не решает правила игры. Она знает только экранную геометрию
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

- перемещение group;
- масштаб;
- смена кадра;
- появление или исчезновение;
- переворот карты.

Animation не знает о правилах игры, `GameState` и `GameController`.

## Ownership

```text
GameController -> rules, GameState, input interpretation, VisualCommand
GameScreen     -> pygame adapter, screen frames, command dispatch
Frame     -> local layout, hit-test, frame-owned Action list
Action         -> visual scenario composed from animations
Animation      -> frame-by-frame visual state change
Group       -> passive drawable object
```


