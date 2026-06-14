"""Console launcher for visual animation dev scenarios."""

from __future__ import annotations

import argparse
import os
import sys
from textwrap import dedent


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from tools import activity_sandbox  # noqa: E402


DEFAULT_SCENARIO = "bot_turn"


def main(argv=None):
    args = normalize_argv(list(sys.argv[1:] if argv is None else argv))
    parser = build_parser()

    if not args:
        parser.print_help()
        return 0

    namespace = parser.parse_args(args)
    return int(namespace.handler(namespace) or 0)


def normalize_argv(args):
    """Support short dev forms while keeping argparse as the command parser."""
    if not args:
        return args

    command = args[0]
    if command in activity_sandbox.SCENARIOS:
        return ["run", *args]
    if command.startswith("-") and command not in ("-h", "--help"):
        return ["run", DEFAULT_SCENARIO, *args]
    return args


def build_parser():
    parser = argparse.ArgumentParser(
        prog="animation_cli.py",
        description="Run visual animation dev scenarios.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent(
            """\
            Examples:
              python tools/animation_cli.py list
              python tools/animation_cli.py help bot_turn
              python tools/animation_cli.py run bot_turn
              python tools/animation_cli.py run bot_turn --duration 0.2
              python tools/animation_cli.py run player_hand

            Convenience forms:
              python tools/animation_cli.py bot_turn --duration 0.2
              python tools/animation_cli.py player_hand
              python tools/animation_cli.py --duration 0.2
            """
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    help_parser = subparsers.add_parser(
        "help",
        help="Show global help or animation-specific help.",
        description="Show global help or animation-specific help.",
    )
    help_parser.add_argument("animation", nargs="?", choices=sorted(activity_sandbox.SCENARIOS))
    help_parser.set_defaults(handler=lambda args: handle_help(args, parser))

    list_parser = subparsers.add_parser(
        "list",
        help="Show available animations.",
        description="Show available animations.",
    )
    list_parser.set_defaults(handler=handle_list)

    run_parser = subparsers.add_parser(
        "run",
        help="Run one animation scenario.",
        description="Run one animation scenario.",
    )
    scenario_subparsers = run_parser.add_subparsers(dest="animation", required=True)
    for scenario_name in sorted(activity_sandbox.SCENARIOS):
        scenario_config = activity_sandbox.SCENARIOS[scenario_name]
        scenario_parser = scenario_subparsers.add_parser(
            scenario_name,
            help=scenario_config.description,
            description=scenario_config.description,
        )
        scenario_config.configure_parser(scenario_parser)
    run_parser.set_defaults(handler=handle_run)

    return parser


def handle_help(args, parser):
    if not args.animation:
        parser.print_help()
        return 0

    scenario_parser = activity_sandbox.build_scenario_parser(
        args.animation,
        prog=f"animation_cli.py run {args.animation}",
    )
    scenario_parser.print_help()
    return 0


def handle_list(_args):
    print("Available animations:")
    for scenario_name in sorted(activity_sandbox.SCENARIOS):
        scenario_config = activity_sandbox.SCENARIOS[scenario_name]
        print(f"  {scenario_name:<14} {scenario_config.description}")
    return 0


def handle_run(args):
    return activity_sandbox.run_scenario(args.animation, args)


if __name__ == "__main__":
    raise SystemExit(main())
