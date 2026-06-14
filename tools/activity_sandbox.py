"""Runtime sandbox for manually testable visual activities."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

@dataclass(frozen=True)
class AnimationScenario:
    name: str
    description: str
    configure_parser: object
    create_activity: object


SCENARIOS = {}


def scenario(name, description, configure_parser):
    def decorator(factory):
        SCENARIOS[name] = AnimationScenario(
            name=name,
            description=description,
            configure_parser=configure_parser,
            create_activity=factory,
        )
        return factory

    return decorator


def configure_bot_turn_parser(parser):
    parser.add_argument("--duration", type=float, default=0.5145)
    parser.add_argument(
        "--bot-hand-id",
        action="append",
        dest="bot_hand_ids",
        help="Bot hand activity ID. Can be repeated.",
    )
    parser.add_argument(
        "--target-slot-id",
        action="append",
        dest="target_slot_ids",
        help="Target slot activity/frame ID. Can be repeated.",
    )
    parser.add_argument("--no-clear-start", action="store_true")
    parser.add_argument("--no-clear-between-bots", action="store_true")


def build_parser(prog=None):
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Run a focused activity sandbox.",
    )
    subparsers = parser.add_subparsers(dest="scenario", required=True)

    for scenario_name in sorted(SCENARIOS):
        scenario_config = SCENARIOS[scenario_name]
        scenario_parser = subparsers.add_parser(
            scenario_name,
            help=scenario_config.description,
            description=scenario_config.description,
        )
        scenario_config.configure_parser(scenario_parser)

    return parser


def build_scenario_parser(scenario_name, prog=None):
    scenario_config = SCENARIOS[scenario_name]
    parser = argparse.ArgumentParser(
        prog=prog or scenario_name,
        description=scenario_config.description,
    )
    scenario_config.configure_parser(parser)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_scenario(args.scenario, args)


def run_scenario(scenario_name, args):
    from core.render_engine import RenderEngine
    from main import build_app_context, create_screen_factory

    app_context = build_app_context()
    base_screen_factory = create_screen_factory(app_context)
    scenario_config = SCENARIOS[scenario_name]

    def screen_factory(render_context=None):
        screen = base_screen_factory(render_context)
        activity = scenario_config.create_activity(screen, args)
        if activity is not None and activity not in getattr(screen, "active_activities", ()):
            screen.add_activity(activity)
        return screen

    render_engine = RenderEngine(
        screen_factory=screen_factory,
        screen_size=app_context["screen_size"],
        title=f"{app_context['window_title']} - activity sandbox: {scenario_name}",
    )
    render_engine.run()
    return 0


@scenario(
    "bot_turn",
    "Run the full bot turn animation sandbox.",
    configure_bot_turn_parser,
)
def create_bot_turn_activity(screen, args):
    from activities import BotTurnActivity

    return BotTurnActivity(
        bot_hand_ids=tuple(
            args.bot_hand_ids
            or ("top_player_hand", "left_player_hand", "right_player_hand")
        ),
        target_slot_ids=tuple(args.target_slot_ids or screen.get_play_area_slot_ids_by_position()),
        get_activity=screen.get_named_activity,
        get_frame=screen.get_screen_frame,
        duration=args.duration,
        reset_overlay_on_start=not args.no_clear_start,
        clear_between_bots=not args.no_clear_between_bots,
    )


def configure_player_hand_parser(parser):
    parser.add_argument(
        "--activity-id",
        default="bottom_player_hand",
        help="Named player hand activity to inspect.",
    )


@scenario(
    "player_hand",
    "Run the lower player hand activity sandbox.",
    configure_player_hand_parser,
)
def create_player_hand_activity(screen, args):
    return screen.get_named_activity(args.activity_id)


if __name__ == "__main__":
    raise SystemExit(main())
