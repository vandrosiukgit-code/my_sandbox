"""Runtime sandbox for manually testable visual activities."""

from __future__ import annotations

import argparse
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from activities import BotTurnActivity  # noqa: E402
from core.render_engine import RenderEngine  # noqa: E402
from main import build_app_context, create_screen_factory  # noqa: E402


SCENARIOS = {}


def scenario(name):
    def decorator(factory):
        SCENARIOS[name] = factory
        return factory

    return decorator


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a focused activity sandbox.")
    parser.add_argument("scenario", choices=sorted(SCENARIOS))
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
    args = parser.parse_args(argv)

    app_context = build_app_context()
    base_screen_factory = create_screen_factory(app_context)
    scenario_factory = SCENARIOS[args.scenario]

    def screen_factory(render_context=None):
        screen = base_screen_factory(render_context)
        activity = scenario_factory(screen, args)
        screen.add_activity(activity)
        return screen

    render_engine = RenderEngine(
        screen_factory=screen_factory,
        screen_size=app_context["screen_size"],
        title=f"{app_context['window_title']} - activity sandbox: {args.scenario}",
    )
    render_engine.run()


@scenario("bot_turn")
def create_bot_turn_activity(screen, args):
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


if __name__ == "__main__":
    main()
