"""Argparse launcher for isolated visual Action checks.

This runner is a dev harness. It prepares enough visual state to run one
Action without starting main.py or game rules.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)


@dataclass(frozen=True)
class ActionRun:
    name: str
    description: str
    expected_result: str
    configure_parser: object
    run: object


ACTION_RUNS = {}


def action_run(name, description, expected_result, configure_parser):
    def decorator(factory):
        ACTION_RUNS[name] = ActionRun(
            name=name,
            description=description,
            expected_result=expected_result,
            configure_parser=configure_parser,
            run=factory,
        )
        return factory

    return decorator


def main(argv=None):
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        return run_interactive(parser)
    args = parser.parse_args(argv)
    return int(args.handler(args) or 0)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="action_runner.py",
        description="Run isolated visual Action checks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List runnable actions.")
    list_parser.set_defaults(handler=handle_list)

    help_parser = subparsers.add_parser("help", help="Show general or action help.")
    help_parser.add_argument("action", nargs="?")
    help_parser.set_defaults(handler=lambda args: handle_help(args, parser))

    run_parser = subparsers.add_parser("run", help="Run one action.")
    run_parser.add_argument("action")
    run_parser.add_argument("action_args", nargs=argparse.REMAINDER)
    run_parser.set_defaults(handler=handle_run)

    return parser


def run_interactive(parser):
    print_banner()
    last_run_command = None
    current_process = None
    while True:
        current_process = clear_finished_process(current_process)
        try:
            command_line = input("action_runner> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            stop_process(current_process)
            return 0

        if not command_line:
            continue
        if command_line in ("quit", "exit", "q"):
            stop_process(current_process)
            return 0
        if command_line == "reload":
            if last_run_command is None:
                print("No previous run command to reload.")
                continue
            stop_process(current_process)
            command_line = last_run_command
            print(f"Reloading: {command_line}")

        try:
            command_args = shlex.split(command_line)
            args = parser.parse_args(command_args)
            if command_args and command_args[0] == "run":
                stop_process(current_process)
                current_process = start_run_process(command_args)
                last_run_command = command_line
                result = 0
            else:
                result = int(args.handler(args) or 0)
        except SystemExit:
            result = 2
        except Exception as error:
            print(f"Error: {error}")
            result = 1

        if result != 0:
            print(f"Command failed: {result}")


def print_banner():
    print("Action runner")
    print("Isolated visual Action checks.")
    print()
    print("Available actions:")
    for index, action in enumerate(iter_actions(), start=1):
        print(f"  {index}. {action.name:<18} {action.description}")
    print()
    print("Commands:")
    print("  list")
    print("  help")
    print("  help <action>")
    print("  help <number>")
    print("  run <action> [options]")
    print("  run <number> [options]")
    print("  reload")
    print("  quit")
    print()
    print("Example:")
    print("  run 1")
    print()


def start_run_process(command_args):
    process = subprocess.Popen([sys.executable, __file__, *command_args])
    print(f"Started action process: pid={process.pid}")
    return process


def clear_finished_process(process):
    if process is None:
        return None
    exit_code = process.poll()
    if exit_code is None:
        return process
    print(f"Action process exited: {exit_code}")
    return None


def stop_process(process):
    if process is None or process.poll() is not None:
        return
    print(f"Stopping action process: pid={process.pid}")
    process.terminate()
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2.0)


def handle_list(_args):
    print("Available actions:")
    for index, action in enumerate(iter_actions(), start=1):
        print(f"  {index}. {action.name:<18} {action.description}")
    return 0


def handle_help(args, parser):
    if not args.action:
        parser.print_help()
        return 0

    action = resolve_action(args.action)
    if action is None:
        print(f"Unknown action: {args.action}")
        print("Run: action_runner.py list")
        return 2

    action_parser = build_action_parser(action)
    action_parser.print_help()
    print()
    print("Expected result:")
    print(action.expected_result)
    return 0


def build_action_parser(action):
    parser = argparse.ArgumentParser(
        prog=f"action_runner.py run {action.name}",
        description=action.description,
    )
    action.configure_parser(parser)
    return parser


def handle_run(args):
    action = resolve_action(args.action)
    if action is None:
        print(f"Unknown action: {args.action}")
        print("Run: action_runner.py list")
        return 2
    action_parser = build_action_parser(action)
    action_args = action_parser.parse_args(args.action_args)
    return action.run(action_args)


def iter_actions():
    return tuple(ACTION_RUNS[name] for name in sorted(ACTION_RUNS))


def resolve_action(action_id):
    if action_id is None:
        return None
    if action_id in ACTION_RUNS:
        return ACTION_RUNS[action_id]
    try:
        index = int(action_id)
    except (TypeError, ValueError):
        return None
    actions = iter_actions()
    if index < 1 or index > len(actions):
        return None
    return actions[index - 1]


def configure_player_card_play_parser(parser):
    parser.add_argument("--duration", type=float, default=0.35)
    parser.add_argument("--target-slot-id", default="cards_slot_frame")
    parser.add_argument("--card-index-from-end", type=int, default=0)
    parser.add_argument("--slot-card-index", type=int)
    parser.add_argument("--resource-key")


def configure_bot_turn_parser(parser):
    parser.add_argument("--duration", type=float, default=0.5145)
    parser.add_argument("--bot-hand-id", action="append", dest="bot_hand_ids")
    parser.add_argument("--target-slot-id", action="append", dest="target_slot_ids")
    parser.add_argument("--no-clear-between-bots", action="store_true")
    parser.add_argument("--slot-card-position", action="append", dest="slot_card_positions")
    parser.add_argument("--bot-card-resource-key")


def configure_start_game_parser(parser):
    parser.add_argument("--card-count", type=int, default=6)
    parser.add_argument("--duration", type=float, default=0.18)
    parser.add_argument("--recipient", action="append", dest="recipient_order")


@action_run(
    "player_card_play",
    "Move one lower-player card into a play-area slot.",
    (
        "One visible card flies from bottom_player_hand to the target slot, "
        "then the flight group is removed and the slot receives the card."
    ),
    configure_player_card_play_parser,
)
def run_player_card_play(args):
    from core import GameController
    from core.render_engine import RenderEngine
    from core.resource import ResourceManager
    from group import GroupStore
    from screens.table_screen import TableScreen

    game_controller = GameController(GameController.create_fixture_state())
    group_store = GroupStore(resource_manager=ResourceManager)

    def screen_factory(_render_context=None):
        ResourceManager.build_runtime_cache(ASSETS_DIR)
        group_store.build()
        screen = TableScreen(
            group_store=group_store,
            game_controller=game_controller,
        )
        prepare_isolated_screen(screen)
        start_player_card_play(screen, args)
        return screen

    render_engine = RenderEngine(
        screen_factory=screen_factory,
        screen_size=(1280, 720),
        title="The Fool's Reef - action: player_card_play",
    )
    render_engine.run()
    return 0


@action_run(
    "bot_turn",
    "Move bot cards into play-area slots.",
    (
        "BotTurnActivity selects bot-hand cards, flies them to the central "
        "slot, and PlayAreaSlotsActivity owns slot placement."
    ),
    configure_bot_turn_parser,
)
def run_bot_turn(args):
    from activities import BotTurnActivity
    from core import GameController
    from core.render_engine import RenderEngine
    from core.resource import ResourceManager
    from group import GroupStore
    from screens.table_screen import TableScreen

    game_controller = GameController(GameController.create_fixture_state())
    group_store = GroupStore(resource_manager=ResourceManager)

    def screen_factory(_render_context=None):
        ResourceManager.build_runtime_cache(ASSETS_DIR)
        group_store.build()
        screen = TableScreen(
            group_store=group_store,
            game_controller=game_controller,
        )
        prepare_isolated_screen(screen)
        start_bot_turn(screen, args, BotTurnActivity)
        return screen

    render_engine = RenderEngine(
        screen_factory=screen_factory,
        screen_size=(1280, 720),
        title="The Fool's Reef - activity: bot_turn",
    )
    render_engine.run()
    return 0


@action_run(
    "start_game",
    "Deal opening hands from the deck to every player.",
    (
        "The deck sends one face-down card in counter-clockwise order to the "
        "lower player and three bots until every hand has six cards."
    ),
    configure_start_game_parser,
)
def run_start_game(args):
    from core import GameController
    from core.render_engine import RenderEngine
    from core.resource import ResourceManager
    from group import GroupStore
    from screens.table_screen import TableScreen

    game_controller = GameController(GameController.create_fixture_state())
    group_store = GroupStore(resource_manager=ResourceManager)

    def screen_factory(_render_context=None):
        ResourceManager.build_runtime_cache(ASSETS_DIR)
        group_store.build()
        screen = TableScreen(
            group_store=group_store,
            game_controller=game_controller,
        )
        prepare_isolated_screen(screen)
        start_start_game(screen, args)
        return screen

    render_engine = RenderEngine(
        screen_factory=screen_factory,
        screen_size=(1280, 720),
        title="The Fool's Reef - activity: start_game",
    )
    render_engine.run()
    return 0


def prepare_isolated_screen(screen):
    """Remove fixture-started transient actions before the requested action."""
    for frame in screen.screen_frames.values():
        frame.actions = []
    if hasattr(screen, "clear_play_area_slot_cards"):
        screen.clear_play_area_slot_cards()
    screen.update(0.0)


def start_bot_turn(screen, args, activity_class):
    play_area_slots_activity = screen.get_play_area_slots_activity()
    if play_area_slots_activity is not None and not getattr(play_area_slots_activity, "started", False):
        play_area_slots_activity.start()

    bot_actions_fixture = load_table_bot_actions_fixture()
    target_slot_ids = tuple(args.target_slot_ids or get_default_bot_turn_target_slot_ids(screen))
    bot_card_resource_key = args.bot_card_resource_key or bot_actions_fixture.get("bot_card_resource_key")
    slot_card_positions = tuple(
        args.slot_card_positions
        or get_default_bot_turn_slot_card_positions(screen)
    )

    bot_turn_activity = activity_class(
        bot_hand_ids=tuple(
            args.bot_hand_ids
            or bot_actions_fixture.get("bot_hand_ids")
            or ("top_player_hand", "left_player_hand", "right_player_hand")
        ),
        target_slot_ids=target_slot_ids,
        get_activity=screen.get_named_activity,
        get_frame=screen.get_screen_frame,
        duration=args.duration,
        clear_between_bots=not args.no_clear_between_bots,
        slot_card_positions=slot_card_positions,
        bot_card_resource_key=bot_card_resource_key,
        freeze_slot_layout=screen.freeze_play_area_slot_layout,
        release_slot_layout=screen.release_play_area_slot_layout,
    )
    screen.add_activity(bot_turn_activity)


def start_start_game(screen, args):
    activity = screen.get_named_activity("start_game")
    if activity is None:
        raise RuntimeError("Missing start_game activity")
    activity.deal_duration = max(0.0, float(args.duration))
    if not activity.start_scenario(
        card_count=max(0, int(args.card_count)),
        recipient_order=args.recipient_order,
    ):
        raise RuntimeError("start_game scenario is already active")


def load_table_bot_actions_fixture():
    fixture_path = os.path.join(PROJECT_DIR, "fixtures", "table_screen_fixture.json")
    try:
        with open(fixture_path, "r", encoding="utf-8") as fixture_file:
            fixture = json.load(fixture_file)
    except (OSError, json.JSONDecodeError):
        return {}
    bot_actions = fixture.get("bot_actions", {})
    return bot_actions if isinstance(bot_actions, dict) else {}


def get_default_bot_turn_target_slot_ids(screen):
    play_area_slots_activity = screen.get_play_area_slots_activity()
    slot_ids = tuple(getattr(play_area_slots_activity, "managed_slot_ids", ()))
    if slot_ids:
        return slot_ids[:1]
    return ("cards_slot_frame",)


def get_default_bot_turn_slot_card_positions(screen):
    play_area_slots_activity = screen.get_play_area_slots_activity()
    slot_count = max(1, len(tuple(getattr(play_area_slots_activity, "managed_slot_ids", ()))) or 1)
    central_activity = None
    if hasattr(play_area_slots_activity, "get_central_slot_activity"):
        central_activity = play_area_slots_activity.get_central_slot_activity()
    max_cards = getattr(central_activity, "max_cards", 2) if central_activity is not None else 2
    return tuple("first" for _index in range(slot_count * max(1, int(max_cards))))


def start_player_card_play(screen, args):
    hand_activity = screen.get_named_activity("bottom_player_hand")
    if hand_activity is None:
        raise RuntimeError("Missing bottom_player_hand activity")

    groups = tuple(hand_activity.iter_generated_groups())
    if not groups:
        raise RuntimeError("bottom_player_hand has no generated cards")

    group_index = max(0, int(args.card_index_from_end))
    if group_index >= len(groups):
        raise RuntimeError(f"card index from end is out of range: {group_index}")

    group = groups[-1 - group_index]
    turn_context = hand_activity.build_selected_card_intent(group)
    turn_context["target_slot_id"] = args.target_slot_id
    if args.slot_card_index is not None:
        turn_context["slot_card_index"] = args.slot_card_index
    if args.resource_key:
        turn_context["card_id"] = args.resource_key
        turn_context["resource_key"] = args.resource_key

    player_turn_activity = screen.get_named_activity("play_area_frame")
    if player_turn_activity is None:
        raise RuntimeError("Missing play_area_frame player turn activity")

    started = player_turn_activity.start_turn(turn_context)
    if not started or player_turn_activity.current_action is None:
        raise RuntimeError("player_card_play action was not started")

    current_action = player_turn_activity.current_action
    for animation in getattr(current_action, "animations", ()):
        if hasattr(animation, "duration"):
            animation.duration = max(0.0, float(args.duration))


if __name__ == "__main__":
    raise SystemExit(main())
