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
move_group
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

`Activity` is a long-lived visual behavior mode/process. It can live for one
frame, for a phase, or for the whole game session. For example, a player hand
activity can lay out cards, react to hover, accept visual commands, and start
short actions.

An activity may also own generated visual-only groups. For example,
`BotHandActivity` can receive a card-back `resource_key` and `card_count`,
create that many card-back groups, place them in its frame as a fan, and remove
extra groups when the count decreases. These groups are screen representations
of controller data. They do not create, delete, or mutate game entities.

```python
VisualCommand(
    type="start_activity",
    activity="group.activate",
    target="table.surface",
)
```

The base screen supports `group.activate` and `group.deactivate`. Future terms
such as `player.hand`, `table.zone`, or `drag.card` should remain public
manifest terms and be mapped by concrete screens to real activity objects.

Example payload for a bot hand activity:

```python
VisualCommand(
    type="start_activity",
    activity="bot.hand",
    payload={
        "frame_id": "left_player_hand",
        "resource_key": "cards.card_back",
        "card_count": 8,
    },
)
```

## Action Terms

`Action` is a short finite visual step. It starts, updates over time, and
completes. Examples include moving a card from A to B, flipping a card, playing
a flash, or scaling a group. An action can be owned by a screen, a frame, or a
long-lived activity.

## Move Group Action

`move_group` creates a frame-owned `MoveGroupAction` and moves one runtime
`Group` in screen coordinates:

```python
VisualCommand(
    type="move_group",
    group_id="left_player",
    payload={
        "to": (80, 260),
        "duration": 0.25,
    },
)
```

The target can also be expressed as a frame-local position:

```python
VisualCommand(
    type="move_group",
    group_id="left_player",
    payload={
        "frame_id": "left_player_portrait",
        "local_pos": (0, 0),
        "duration": 0.25,
    },
)
```

The action lives in the frame that currently owns `group_id`, and the lower
level `MoveGroupAnimation` changes only `group.set_position(...)`.
