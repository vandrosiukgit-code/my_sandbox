# Visual Input Flow

`GameScreen` adapts raw pygame input to controller input and applies controller
visual commands through `GuiManifest`.

## Input Path

```text
pygame event
    -> GameScreen.build_input_event()
    -> GameScreen.hit_test()
        -> root Frame tree
        -> child Frame tree
        -> active group hit_rect
    -> ScreenInputEvent
    -> GameController.handle_input()
```

`ScreenInputEvent` describes a visual fact:

```text
type        click | double_click
button      left | right | middle | wheel_up | wheel_down
group_id    group under cursor, if any
frame_id    frame under cursor, if any
screen_pos  pygame screen coordinates
local_pos   frame-local coordinates
raw_event   original pygame event
```

It does not contain game meaning. A click on a group is only an input fact; the
controller decides whether it matters.

## Output Path

```text
GameController.handle_input()
    -> VisualCommand objects
    -> GameScreen.dispatch_visual_command()
    -> GuiManifest target/activity resolution
    -> GroupStore
    -> group_config.py
    -> runtime Group layer refresh
    -> GameScreen.draw()
```

Current `VisualCommand` fields:

```text
type
target
value
activity
group_id
from_frame
to_frame
payload
```

Supported base command types:

```text
set_resource
set_text
start_activity
activate_group
deactivate_group
```

## Example Resource Update

```python
VisualCommand(
    type="set_resource",
    target="player.left.avatar",
    value="main_screen.avatars.portrait_4",
)
```

Resolution:

```text
player.left.avatar
    -> GuiTarget(type="resource", group_id="left_player", layer="portrait")
    -> GroupStore.set_group_layer_resource(...)
    -> group_config.set_layer_resource(...)
    -> Group.replace_layer(...)
```

## Example Text Update

```python
VisualCommand(
    type="set_text",
    target="player.left.name",
    value="Captain",
)
```

Resolution:

```text
player.left.name
    -> GuiTarget(type="text", group_id="left_player", layer="player_name_text")
    -> GroupStore.set_group_layer_text(...)
    -> group_config.set_layer_text(...)
    -> Group.replace_layer(...)
```

## Activity Terms

```python
VisualCommand(
    type="start_activity",
    activity="group.activate",
    target="table.surface",
)
```

The base screen supports `group.activate` and `group.deactivate`. Future terms
such as `card.move`, `card.flip`, or `player.highlight` should remain public
manifest terms and be mapped by concrete screens to real visual processes.
