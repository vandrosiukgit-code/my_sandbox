# Visual Input Flow

`GameScreen` adapts pygame input to controller input and applies controller
visual commands through `GuiManifest`.

```text
pygame event
    -> GameScreen
    -> Frame hit-test
    -> ScreenInputEvent
    -> GameController.handle_input()
    -> VisualCommand
    -> GuiManifest target/activity resolution
    -> GroupStore
    -> Group refresh/draw
```

## Input

`ScreenInputEvent` describes a raw visual fact:

```text
type        click | double_click
button      left | right | middle
group_id    group under cursor
frame_id    frame under cursor
screen_pos  pygame screen coordinates
local_pos   frame-local coordinates
```

It does not contain game meaning.

## Output

`VisualCommand` uses public GUI terms:

```python
VisualCommand(
    type="set_resource",
    target="player.left.avatar",
    value="main_screen.avatars.portrait_4",
)
```

`GameScreen` resolves `player.left.avatar` to:

```text
group_id = left_player
layer    = portrait
```

and delegates to `GroupStore`, which updates `group_config.json` through
`group_config.py` and refreshes the runtime layer.

## Activity Terms

Activity commands also use public names:

```python
VisualCommand(
    type="start_activity",
    activity="group.activate",
    target="table.surface",
)
```

The base screen supports `group.activate` and `group.deactivate`. Later screens
can map terms such as `card.move` or `player.highlight` to concrete visual
processes.
