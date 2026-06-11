from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    from .core import (
        build_facade_audit,
        build_protocol_audit,
        compact_help,
        render_class_diagram,
        render_code_map,
        render_facade_audit,
        render_facade_audit_json,
        render_protocol_audit,
        render_protocol_audit_json,
    )

    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if effective_argv and effective_argv[0] not in {"help", "map", "class-diagram", "facade-audit", "protocol-audit"} and not effective_argv[0].startswith("-"):
        effective_argv = ["map", *effective_argv]

    parser = argparse.ArgumentParser(description="Print AST maps and generate PlantUML class diagrams.")
    subparsers = parser.add_subparsers(dest="command")

    help_parser = subparsers.add_parser("help", help="Print compact CLI synopsis.")
    help_parser.set_defaults(handler=lambda _args: _print_help(compact_help()))

    map_parser = subparsers.add_parser("map", help="Print class/function map for a Python file.")
    map_parser.add_argument("file_path")
    map_parser.set_defaults(handler=lambda args: _render_code_map(args, render_code_map))

    diagram_parser = subparsers.add_parser("class-diagram", help="Generate PlantUML class diagram from Python sources.")
    diagram_parser.add_argument("target_path")
    diagram_parser.add_argument("output", nargs="?")
    diagram_parser.set_defaults(handler=lambda args: _render_class_diagram(args, render_class_diagram))

    audit_parser = subparsers.add_parser(
        "facade-audit",
        help="Audit a class facade surface, wrapper methods, and caller roots.",
    )
    audit_parser.add_argument("file_path")
    audit_parser.add_argument("--symbol", required=True)
    audit_parser.add_argument("--callers", nargs="+", required=True)
    audit_parser.add_argument("--json", action="store_true")
    audit_parser.add_argument("--include-private", action="store_true")
    audit_parser.set_defaults(
        handler=lambda args: _render_facade_audit(
            args,
            build_facade_audit,
            render_facade_audit,
            render_facade_audit_json,
        )
    )

    protocol_parser = subparsers.add_parser(
        "protocol-audit",
        help="Audit protocol/bridge surfaces, GameSession mirrors, and feature owner mixes.",
    )
    protocol_parser.add_argument("target_path")
    protocol_parser.add_argument("--symbol")
    protocol_parser.add_argument("--json", action="store_true")
    protocol_parser.add_argument("--include-private", action="store_true")
    protocol_parser.add_argument("--facade-file")
    protocol_parser.add_argument("--facade-symbol", default="GameSession")
    protocol_parser.set_defaults(
        handler=lambda args: _render_protocol_audit(
            args,
            build_protocol_audit,
            render_protocol_audit,
            render_protocol_audit_json,
        )
    )

    args = parser.parse_args(effective_argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 0
    return int(args.handler(args) or 0)


def _print_help(text: str) -> int:
    print(text)
    return 0


def _resolve_target(path_text: str) -> Path:
    target = Path(path_text)
    if not target.is_absolute():
        target = (PROJECT_ROOT / target).resolve()
    return target


def _render_code_map(args: argparse.Namespace, render_code_map: object) -> int:
    target = _resolve_target(args.file_path)
    print(render_code_map(target, PROJECT_ROOT))
    return 0


def _render_class_diagram(args: argparse.Namespace, render_class_diagram: object) -> int:
    target = _resolve_target(args.target_path)
    output = render_class_diagram(target, PROJECT_ROOT)
    if args.output:
        output_path = _resolve_target(args.output)
        output_path.write_text(output, encoding="utf-8")
        print(output_path)
        return 0
    print(output, end="")
    return 0


def _render_facade_audit(
    args: argparse.Namespace,
    build_facade_audit: object,
    render_facade_audit: object,
    render_facade_audit_json: object,
) -> int:
    target = _resolve_target(args.file_path)
    caller_roots = tuple(_resolve_target(path_text) for path_text in args.callers)
    report = build_facade_audit(
        target,
        args.symbol,
        caller_roots,
        PROJECT_ROOT,
        include_private=args.include_private,
    )
    if args.json:
        print(render_facade_audit_json(report, PROJECT_ROOT))
        return 0
    print(render_facade_audit(report, PROJECT_ROOT))
    return 0


def _render_protocol_audit(
    args: argparse.Namespace,
    build_protocol_audit: object,
    render_protocol_audit: object,
    render_protocol_audit_json: object,
) -> int:
    target = _resolve_target(args.target_path)
    facade_file_path = None if args.facade_file is None else _resolve_target(args.facade_file)
    report = build_protocol_audit(
        target,
        PROJECT_ROOT,
        symbol=args.symbol,
        include_private=args.include_private,
        facade_file_path=facade_file_path,
        facade_symbol=args.facade_symbol,
    )
    if args.json:
        print(render_protocol_audit_json(report, PROJECT_ROOT))
        return 0
    print(render_protocol_audit(report, PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
