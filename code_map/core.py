from __future__ import annotations

import ast
import builtins
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodeMapNode:
    kind: str
    name: str
    start_line: int
    end_line: int
    children: tuple["CodeMapNode", ...]


@dataclass(frozen=True)
class CodeMapReport:
    file_path: Path
    nodes: tuple[CodeMapNode, ...]


@dataclass(frozen=True)
class ClassField:
    name: str
    annotation: str | None
    start_line: int
    inferred: bool = False


@dataclass(frozen=True)
class ClassMethod:
    name: str
    kind: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class ClassInfo:
    module_name: str
    qualified_name: str
    file_path: Path
    name: str
    start_line: int
    end_line: int
    bases: tuple[str, ...]
    fields: tuple[ClassField, ...]
    methods: tuple[ClassMethod, ...]


@dataclass(frozen=True)
class ClassRelation:
    kind: str
    source: str
    target: str
    label: str | None = None


@dataclass(frozen=True)
class ClassDiagramReport:
    target_path: Path
    classes: tuple[ClassInfo, ...]
    relations: tuple[ClassRelation, ...]


@dataclass(frozen=True)
class FacadeCallSite:
    file_path: Path
    line: int
    column: int
    receiver: str
    enclosing_symbol: str | None
    layer: str
    access_kind: str


@dataclass(frozen=True)
class FacadeDelegation:
    kind: str
    expression: str
    target: str | None
    target_group: str


@dataclass(frozen=True)
class FacadeMethodAudit:
    name: str
    start_line: int
    end_line: int
    visibility: str
    categories: tuple[str, ...]
    layer_counts: tuple[tuple[str, int], ...]
    delegation: FacadeDelegation | None
    call_sites: tuple[FacadeCallSite, ...]


@dataclass(frozen=True)
class FacadeAuditReport:
    file_path: Path
    symbol: str
    methods: tuple[FacadeMethodAudit, ...]
    caller_roots: tuple[Path, ...]


@dataclass(frozen=True)
class ProtocolContract:
    feature: str
    qualified_name: str
    members: tuple[str, ...]


@dataclass(frozen=True)
class ProtocolMemberAudit:
    name: str
    kind: str
    start_line: int
    end_line: int
    categories: tuple[str, ...]
    owner_features: tuple[str, ...]
    replacement_contracts: tuple[str, ...]
    delegation: FacadeDelegation | None


@dataclass(frozen=True)
class ProtocolTypeAudit:
    file_path: Path
    name: str
    qualified_name: str
    kind: str
    start_line: int
    end_line: int
    bases: tuple[str, ...]
    base_contracts: tuple[str, ...]
    owner_features: tuple[str, ...]
    categories: tuple[str, ...]
    members: tuple[ProtocolMemberAudit, ...]


@dataclass(frozen=True)
class ProtocolAuditReport:
    target_path: Path
    file_path: Path | None
    symbol: str | None
    facade_file_path: Path | None
    facade_symbol: str | None
    classes: tuple[ProtocolTypeAudit, ...]


@dataclass(frozen=True)
class _SurfaceMemberSpec:
    name: str
    kind: str
    start_line: int
    end_line: int
    node: ast.AST | None


def build_code_map(file_path: Path) -> CodeMapReport:
    source = file_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(file_path))
    nodes = tuple(_build_nodes(tree.body))
    return CodeMapReport(file_path=file_path, nodes=nodes)


def render_code_map(file_path: Path, project_root: Path | None = None) -> str:
    report = build_code_map(file_path)
    label = _display_path(report.file_path, project_root)
    lines = [label]
    for node in report.nodes:
        lines.extend(_render_node(node, depth=0))
    return "\n".join(lines)


def build_class_diagram(target_path: Path, project_root: Path) -> ClassDiagramReport:
    resolved_target = target_path.resolve()
    python_files = _collect_python_files(resolved_target)
    module_reports = [_parse_module(file_path, project_root) for file_path in python_files]
    class_index = {
        class_info.qualified_name: class_info
        for module_report in module_reports
        for class_info in module_report.classes
    }
    relations: set[ClassRelation] = set()
    for module_report in module_reports:
        resolver = _NameResolver(module_report.module_name, module_report.imports, class_index)
        for class_info in module_report.classes:
            for raw_base in class_info.bases:
                resolved = resolver.resolve_reference(raw_base)
                if resolved is None or resolved == class_info.qualified_name:
                    continue
                relations.add(ClassRelation("inheritance", class_info.qualified_name, resolved))
            for field in class_info.fields:
                if field.annotation is None:
                    continue
                for candidate in _type_reference_names(field.annotation):
                    resolved = resolver.resolve_reference(candidate)
                    if resolved is None or resolved == class_info.qualified_name:
                        continue
                    relations.add(
                        ClassRelation(
                            "composition",
                            class_info.qualified_name,
                            resolved,
                            label=field.name,
                        )
                    )
    classes = tuple(sorted(class_index.values(), key=lambda item: (item.module_name, item.name, item.start_line)))
    sorted_relations = tuple(
        sorted(relations, key=lambda item: (item.kind, item.source, item.target, item.label or ""))
    )
    return ClassDiagramReport(target_path=resolved_target, classes=classes, relations=sorted_relations)


def render_class_diagram(target_path: Path, project_root: Path) -> str:
    report = build_class_diagram(target_path, project_root)
    grouped: dict[str, list[ClassInfo]] = {}
    for class_info in report.classes:
        grouped.setdefault(class_info.module_name, []).append(class_info)

    lines = [
        "@startuml",
        "hide empty members",
        "skinparam classAttributeIconSize 0",
    ]
    for module_name in sorted(grouped):
        lines.append(f'package "{module_name}" {{')
        for class_info in grouped[module_name]:
            alias = _alias_for_class(class_info.qualified_name)
            lines.append(f'  class "{class_info.name}" as {alias} {{')
            for field in class_info.fields:
                field_type = field.annotation or "Any"
                prefix = "~" if field.inferred else "+"
                lines.append(f"    {prefix}{field.name}: {field_type}")
            if class_info.fields and class_info.methods:
                lines.append("    --")
            for method in class_info.methods:
                method_prefix = "+" if method.kind == "method" else "+{static}"
                lines.append(f"    {method_prefix}{method.name}()")
            lines.append("  }")
        lines.append("}")
    for relation in report.relations:
        source_alias = _alias_for_class(relation.source)
        target_alias = _alias_for_class(relation.target)
        if relation.kind == "inheritance":
            lines.append(f"{source_alias} --|> {target_alias}")
            continue
        label = f" : {relation.label}" if relation.label else ""
        lines.append(f"{source_alias} *-- {target_alias}{label}")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def build_facade_audit(
    file_path: Path,
    symbol: str,
    caller_roots: tuple[Path, ...],
    project_root: Path,
    *,
    include_private: bool = False,
) -> FacadeAuditReport:
    source = file_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(file_path))
    module_name = _module_name_for_file(file_path, project_root)
    imports = _import_aliases(tree, module_name)
    class_node = _find_class_node(tree, symbol, file_path)
    member_specs = [
        spec
        for spec in _class_surface_members(class_node, include_private=include_private, include_attributes=False)
        if spec.node is not None
    ]

    caller_files = _collect_caller_files(caller_roots)
    call_map = _collect_member_access_sites(
        caller_files,
        tuple(spec.name for spec in member_specs),
        project_root,
    )
    methods: list[FacadeMethodAudit] = []
    for member_spec in member_specs:
        assert member_spec.node is not None
        delegation = _member_delegation(member_spec, imports, module_name)
        call_sites = tuple(
            sorted(
                call_map.get(member_spec.name, ()),
                key=lambda item: (_display_path(item.file_path, project_root), item.line, item.column, item.access_kind),
            )
        )
        layer_counts = _sorted_layer_counts(call_sites)
        categories = _method_categories(call_sites, delegation)
        methods.append(
            FacadeMethodAudit(
                name=member_spec.name,
                start_line=member_spec.start_line,
                end_line=member_spec.end_line,
                visibility="private" if member_spec.name.startswith("_") else "public",
                categories=categories,
                layer_counts=layer_counts,
                delegation=delegation,
                call_sites=call_sites,
            )
        )
    return FacadeAuditReport(
        file_path=file_path,
        symbol=symbol,
        methods=tuple(methods),
        caller_roots=tuple(root.resolve() for root in caller_roots),
    )


def render_facade_audit(report: FacadeAuditReport, project_root: Path | None = None) -> str:
    label = _display_path(report.file_path, project_root)
    caller_roots = ", ".join(_display_path(root, project_root) for root in report.caller_roots)
    lines = [
        f"{label} :: {report.symbol}",
        f"caller_roots: {caller_roots}",
        f"methods: {len(report.methods)}",
    ]
    for method in report.methods:
        summary = [
            f"{method.start_line}-{method.end_line}",
            f"visibility={method.visibility}",
            f"callers={_render_layer_counts(method.layer_counts)}",
        ]
        if method.categories:
            summary.append("categories=" + ",".join(method.categories))
        if method.delegation is not None:
            target = method.delegation.target or method.delegation.expression
            summary.append(f"delegation={method.delegation.kind}")
            summary.append(f"target_group={method.delegation.target_group}")
            summary.append(f"target={target}")
        lines.append(f"- {method.name}: " + " ".join(summary))
        for call_site in method.call_sites:
            file_label = _display_path(call_site.file_path, project_root)
            caller_label = f" {call_site.enclosing_symbol}" if call_site.enclosing_symbol else ""
            lines.append(
                f"  {call_site.layer} {file_label}:{call_site.line} access={call_site.access_kind} "
                f"receiver={call_site.receiver}{caller_label}"
            )
    return "\n".join(lines)


def render_facade_audit_json(report: FacadeAuditReport, project_root: Path | None = None) -> str:
    payload = {
        "file_path": _display_path(report.file_path, project_root),
        "symbol": report.symbol,
        "caller_roots": [_display_path(root, project_root) for root in report.caller_roots],
        "methods": [
            {
                "name": method.name,
                "start_line": method.start_line,
                "end_line": method.end_line,
                "visibility": method.visibility,
                "categories": list(method.categories),
                "layer_counts": {layer: count for layer, count in method.layer_counts},
                "delegation": (
                    None
                    if method.delegation is None
                    else {
                        "kind": method.delegation.kind,
                        "expression": method.delegation.expression,
                        "target": method.delegation.target,
                        "target_group": method.delegation.target_group,
                    }
                ),
                "call_sites": [
                    {
                        "file_path": _display_path(call_site.file_path, project_root),
                        "line": call_site.line,
                        "column": call_site.column,
                        "receiver": call_site.receiver,
                        "enclosing_symbol": call_site.enclosing_symbol,
                        "layer": call_site.layer,
                        "access_kind": call_site.access_kind,
                    }
                    for call_site in method.call_sites
                ],
            }
            for method in report.methods
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def build_protocol_audit(
    target_path: Path,
    project_root: Path,
    *,
    symbol: str | None = None,
    include_private: bool = False,
    facade_file_path: Path | None = None,
    facade_symbol: str | None = "GameSession",
) -> ProtocolAuditReport:
    resolved_target = target_path.resolve()
    contracts = _collect_feature_protocol_contracts(project_root)
    contracts_by_qualified = {contract.qualified_name: contract for contract in contracts}
    contracts_by_member: dict[str, list[ProtocolContract]] = defaultdict(list)
    for contract in contracts:
        for member_name in contract.members:
            contracts_by_member[member_name].append(contract)

    resolved_facade_path = _default_facade_file(project_root) if facade_file_path is None else facade_file_path.resolve()
    facade_members: set[str] = set()
    if resolved_facade_path is not None and facade_symbol:
        try:
            facade_members = _class_surface_member_names(
                resolved_facade_path,
                facade_symbol,
                project_root,
                include_private=include_private,
            )
        except ValueError:
            facade_members = set()

    classes: list[ProtocolTypeAudit] = []
    for file_path in _collect_python_files(resolved_target):
        source = file_path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(file_path))
        module_name = _module_name_for_file(file_path, project_root)
        imports = _import_aliases(tree, module_name)
        for statement in tree.body:
            if not isinstance(statement, ast.ClassDef):
                continue
            if symbol is not None and statement.name != symbol:
                continue
            resolved_bases = _resolved_class_bases(statement, imports, module_name)
            is_protocol = _is_protocol_class(statement, resolved_bases)
            member_specs = _class_surface_members(
                statement,
                include_private=include_private,
                include_attributes=is_protocol,
            )
            base_contracts = tuple(
                sorted(
                    contract.qualified_name
                    for base_name in resolved_bases
                    for contract in [contracts_by_qualified.get(base_name)]
                    if contract is not None
                )
            )
            owner_features = {
                contract.feature
                for base_name in resolved_bases
                for contract in [contracts_by_qualified.get(base_name)]
                if contract is not None
            }
            member_audits: list[ProtocolMemberAudit] = []
            for member_spec in member_specs:
                replacement_contracts = tuple(
                    sorted(
                        contract.qualified_name
                        for contract in contracts_by_member.get(member_spec.name, ())
                    )
                )
                member_owner_features = tuple(
                    sorted(
                        {
                            contract.feature
                            for contract in contracts_by_member.get(member_spec.name, ())
                        }
                    )
                )
                owner_features.update(member_owner_features)
                delegation = _member_delegation(member_spec, imports, module_name)
                categories: list[str] = []
                if member_spec.name in facade_members:
                    categories.append("session_mirror")
                if replacement_contracts:
                    categories.append("replaceable_with_feature_contract")
                if delegation is not None:
                    categories.append("wrapper")
                    if delegation.target_group not in {"self", "unresolved"}:
                        categories.append(f"wrapper_to_{delegation.target_group}")
                if len(member_owner_features) > 1:
                    categories.append("mixed_member_owners")
                member_audits.append(
                    ProtocolMemberAudit(
                        name=member_spec.name,
                        kind=member_spec.kind,
                        start_line=member_spec.start_line,
                        end_line=member_spec.end_line,
                        categories=tuple(categories),
                        owner_features=member_owner_features,
                        replacement_contracts=replacement_contracts,
                        delegation=delegation,
                    )
                )
            class_categories: list[str] = []
            if is_protocol:
                class_categories.append("protocol")
            if base_contracts:
                class_categories.append("feature_protocol_surface")
            if any("session_mirror" in member.categories for member in member_audits):
                class_categories.append("session_mirror")
            if any(member.delegation is not None for member in member_audits):
                class_categories.append("delegating_surface")
            if len(owner_features) > 1:
                class_categories.append("mixed_feature_owners")
            if not _is_protocol_surface_class(
                statement.name,
                is_protocol,
                base_contracts,
                member_audits,
                class_categories,
            ):
                continue
            classes.append(
                ProtocolTypeAudit(
                    file_path=file_path,
                    name=statement.name,
                    qualified_name=f"{module_name}.{statement.name}",
                    kind="protocol" if is_protocol else "class",
                    start_line=statement.lineno,
                    end_line=_end_line(statement),
                    bases=resolved_bases,
                    base_contracts=base_contracts,
                    owner_features=tuple(sorted(owner_features)),
                    categories=tuple(class_categories),
                    members=tuple(member_audits),
                )
            )
    classes.sort(key=lambda item: (_display_path(item.file_path, project_root), item.start_line, item.name))
    return ProtocolAuditReport(
        target_path=resolved_target,
        file_path=resolved_target if resolved_target.is_file() else None,
        symbol=symbol,
        facade_file_path=resolved_facade_path,
        facade_symbol=facade_symbol,
        classes=tuple(classes),
    )


def render_protocol_audit(report: ProtocolAuditReport, project_root: Path | None = None) -> str:
    label = _display_path(report.target_path, project_root)
    lines = [
        f"{label} :: protocol-audit",
        f"classes: {len(report.classes)}",
    ]
    if report.facade_file_path is not None and report.facade_symbol is not None:
        lines.append(
            "facade: "
            + f"{_display_path(report.facade_file_path, project_root)} :: {report.facade_symbol}"
        )
    for class_audit in report.classes:
        summary = [
            f"{class_audit.start_line}-{class_audit.end_line}",
            f"kind={class_audit.kind}",
        ]
        if class_audit.owner_features:
            summary.append("owners=" + ",".join(class_audit.owner_features))
        if class_audit.categories:
            summary.append("categories=" + ",".join(class_audit.categories))
        if class_audit.base_contracts:
            summary.append("base_contracts=" + ",".join(class_audit.base_contracts))
        lines.append(
            f"- {_display_path(class_audit.file_path, project_root)} :: {class_audit.name}: " + " ".join(summary)
        )
        for member in class_audit.members:
            member_summary = [
                f"{member.start_line}-{member.end_line}",
                f"kind={member.kind}",
            ]
            if member.owner_features:
                member_summary.append("owners=" + ",".join(member.owner_features))
            if member.categories:
                member_summary.append("categories=" + ",".join(member.categories))
            if member.replacement_contracts:
                member_summary.append("replaceable_with=" + ",".join(member.replacement_contracts))
            if member.delegation is not None:
                target = member.delegation.target or member.delegation.expression
                member_summary.append(f"delegation={member.delegation.kind}")
                member_summary.append(f"target_group={member.delegation.target_group}")
                member_summary.append(f"target={target}")
            lines.append(f"  - {member.name}: " + " ".join(member_summary))
    return "\n".join(lines)


def render_protocol_audit_json(report: ProtocolAuditReport, project_root: Path | None = None) -> str:
    payload = {
        "target_path": _display_path(report.target_path, project_root),
        "file_path": None if report.file_path is None else _display_path(report.file_path, project_root),
        "symbol": report.symbol,
        "facade_file_path": (
            None
            if report.facade_file_path is None
            else _display_path(report.facade_file_path, project_root)
        ),
        "facade_symbol": report.facade_symbol,
        "classes": [
            {
                "file_path": _display_path(class_audit.file_path, project_root),
                "name": class_audit.name,
                "qualified_name": class_audit.qualified_name,
                "kind": class_audit.kind,
                "start_line": class_audit.start_line,
                "end_line": class_audit.end_line,
                "bases": list(class_audit.bases),
                "base_contracts": list(class_audit.base_contracts),
                "owner_features": list(class_audit.owner_features),
                "categories": list(class_audit.categories),
                "members": [
                    {
                        "name": member.name,
                        "kind": member.kind,
                        "start_line": member.start_line,
                        "end_line": member.end_line,
                        "owner_features": list(member.owner_features),
                        "categories": list(member.categories),
                        "replacement_contracts": list(member.replacement_contracts),
                        "delegation": (
                            None
                            if member.delegation is None
                            else {
                                "kind": member.delegation.kind,
                                "expression": member.delegation.expression,
                                "target": member.delegation.target,
                                "target_group": member.delegation.target_group,
                            }
                        ),
                    }
                    for member in class_audit.members
                ],
            }
            for class_audit in report.classes
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def compact_help() -> str:
    return "\n".join(
        [
            "code_map.py help",
            "code_map.py map <python_file>",
            "code_map.py class-diagram <path> [output.puml]",
            "code_map.py facade-audit <python_file> --symbol <ClassName> --callers <path> [<path> ...] [--json]",
            "code_map.py protocol-audit <path> [--symbol <ClassName>] [--json]",
        ]
    )


@dataclass(frozen=True)
class _ModuleReport:
    module_name: str
    file_path: Path
    classes: tuple[ClassInfo, ...]
    imports: dict[str, str]


class _NameResolver:
    def __init__(self, module_name: str, imports: dict[str, str], class_index: dict[str, ClassInfo]) -> None:
        self._module_name = module_name
        self._imports = imports
        self._class_index = class_index

    def resolve_reference(self, reference: str) -> str | None:
        normalized = reference.strip("'\" ")
        if not normalized:
            return None
        if normalized in self._class_index:
            return normalized
        if normalized in self._imports:
            candidate = self._imports[normalized]
            if candidate in self._class_index:
                return candidate
        module_local = f"{self._module_name}.{normalized}"
        if module_local in self._class_index:
            return module_local
        package_prefix, _, _module_leaf = self._module_name.rpartition(".")
        if package_prefix:
            package_local = f"{package_prefix}.{normalized}"
            if package_local in self._class_index:
                return package_local
        return None


class _MemberAccessVisitor(ast.NodeVisitor):
    def __init__(self, target_members: tuple[str, ...], file_path: Path, project_root: Path) -> None:
        self._target_members = set(target_members)
        self._file_path = file_path
        self._project_root = project_root
        self._symbol_stack: list[str] = []
        self.call_sites: dict[str, list[FacadeCallSite]] = defaultdict(list)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._symbol_stack.append(node.name)
        self.generic_visit(node)
        self._symbol_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._symbol_stack.append(node.name)
        self.generic_visit(node)
        self._symbol_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._symbol_stack.append(node.name)
        self.generic_visit(node)
        self._symbol_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr in self._target_members:
            self._record(node.func, access_kind="call")
            self.visit(node.func.value)
        else:
            self.visit(node.func)
        for argument in node.args:
            self.visit(argument)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load) and node.attr in self._target_members:
            self._record(node, access_kind="attribute")
        self.visit(node.value)

    def _record(self, node: ast.Attribute, *, access_kind: str) -> None:
        receiver = _render_expr(node.value) or "<unknown>"
        self.call_sites[node.attr].append(
            FacadeCallSite(
                file_path=self._file_path,
                line=node.lineno,
                column=node.col_offset,
                receiver=receiver,
                enclosing_symbol=".".join(self._symbol_stack) if self._symbol_stack else None,
                layer=_layer_name(self._file_path, self._project_root),
                access_kind=access_kind,
            )
        )


def _build_nodes(body: list[ast.stmt]) -> list[CodeMapNode]:
    nodes: list[CodeMapNode] = []
    for statement in body:
        if isinstance(statement, ast.ClassDef):
            nodes.append(
                CodeMapNode(
                    kind="class",
                    name=statement.name,
                    start_line=statement.lineno,
                    end_line=_end_line(statement),
                    children=tuple(_build_nodes(statement.body)),
                )
            )
        elif isinstance(statement, ast.FunctionDef):
            nodes.append(
                CodeMapNode(
                    kind="function",
                    name=statement.name,
                    start_line=statement.lineno,
                    end_line=_end_line(statement),
                    children=tuple(_build_nodes(statement.body)),
                )
            )
        elif isinstance(statement, ast.AsyncFunctionDef):
            nodes.append(
                CodeMapNode(
                    kind="async function",
                    name=statement.name,
                    start_line=statement.lineno,
                    end_line=_end_line(statement),
                    children=tuple(_build_nodes(statement.body)),
                )
            )
    return nodes


def _parse_module(file_path: Path, project_root: Path) -> _ModuleReport:
    source = file_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(file_path))
    module_name = _module_name_for_file(file_path, project_root)
    imports = _import_aliases(tree, module_name)
    classes: list[ClassInfo] = []
    for statement in tree.body:
        if not isinstance(statement, ast.ClassDef):
            continue
        qualified_name = f"{module_name}.{statement.name}"
        methods = tuple(_class_methods(statement))
        fields = tuple(_class_fields(statement))
        bases = tuple(sorted({_render_expr(base) for base in statement.bases if _render_expr(base)}))
        classes.append(
            ClassInfo(
                module_name=module_name,
                qualified_name=qualified_name,
                file_path=file_path,
                name=statement.name,
                start_line=statement.lineno,
                end_line=_end_line(statement),
                bases=bases,
                fields=fields,
                methods=methods,
            )
        )
    return _ModuleReport(
        module_name=module_name,
        file_path=file_path,
        classes=tuple(classes),
        imports=imports,
    )


def _class_methods(class_node: ast.ClassDef) -> list[ClassMethod]:
    methods: list[ClassMethod] = []
    for statement in class_node.body:
        if isinstance(statement, ast.FunctionDef):
            methods.append(
                ClassMethod(
                    name=statement.name,
                    kind="method" if _is_instance_method(statement) else "callable",
                    start_line=statement.lineno,
                    end_line=_end_line(statement),
                )
            )
        elif isinstance(statement, ast.AsyncFunctionDef):
            methods.append(
                ClassMethod(
                    name=statement.name,
                    kind="async method" if _is_instance_method(statement) else "async callable",
                    start_line=statement.lineno,
                    end_line=_end_line(statement),
                )
            )
    return methods


def _class_fields(class_node: ast.ClassDef) -> list[ClassField]:
    fields: dict[str, ClassField] = {}
    for statement in class_node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            annotation = _render_expr(statement.annotation)
            fields[statement.target.id] = ClassField(
                name=statement.target.id,
                annotation=annotation,
                start_line=statement.lineno,
                inferred=False,
            )
            continue
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for inner in ast.walk(statement):
            if isinstance(inner, ast.AnnAssign) and _is_self_attribute(inner.target):
                field_name = inner.target.attr
                annotation = _render_expr(inner.annotation)
                fields.setdefault(
                    field_name,
                    ClassField(
                        name=field_name,
                        annotation=annotation,
                        start_line=inner.lineno,
                        inferred=False,
                    ),
                )
                continue
            if isinstance(inner, ast.Assign):
                inferred = _infer_self_assignment(inner)
                if inferred is None:
                    continue
                field_name, annotation = inferred
                fields.setdefault(
                    field_name,
                    ClassField(
                        name=field_name,
                        annotation=annotation,
                        start_line=inner.lineno,
                        inferred=True,
                    ),
                )
    return sorted(fields.values(), key=lambda item: (item.start_line, item.name))


def _find_class_node(tree: ast.Module, symbol: str, file_path: Path) -> ast.ClassDef:
    for statement in tree.body:
        if isinstance(statement, ast.ClassDef) and statement.name == symbol:
            return statement
    raise ValueError(f'class "{symbol}" not found in {file_path}')


def _collect_caller_files(caller_roots: tuple[Path, ...]) -> list[Path]:
    files: set[Path] = set()
    for root in caller_roots:
        resolved_root = root.resolve()
        for file_path in _collect_python_files(resolved_root):
            files.add(file_path.resolve())
    return sorted(files)


def _collect_member_access_sites(
    caller_files: list[Path],
    member_names: tuple[str, ...],
    project_root: Path,
) -> dict[str, tuple[FacadeCallSite, ...]]:
    collected: dict[str, list[FacadeCallSite]] = defaultdict(list)
    for file_path in caller_files:
        source = file_path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(file_path))
        visitor = _MemberAccessVisitor(member_names, file_path, project_root)
        visitor.visit(tree)
        for member_name, call_sites in visitor.call_sites.items():
            collected[member_name].extend(call_sites)
    return {
        member_name: tuple(
            sorted(
                call_sites,
                key=lambda item: (
                    _display_path(item.file_path, project_root),
                    item.line,
                    item.column,
                    item.access_kind,
                ),
            )
        )
        for member_name, call_sites in collected.items()
    }


def _member_delegation(
    member_spec: _SurfaceMemberSpec,
    imports: dict[str, str],
    module_name: str,
) -> FacadeDelegation | None:
    if not isinstance(member_spec.node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    return _method_delegation(member_spec.node, imports, module_name)


def _method_delegation(
    method_node: ast.FunctionDef | ast.AsyncFunctionDef,
    imports: dict[str, str],
    module_name: str,
) -> FacadeDelegation | None:
    body = list(method_node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    if len(body) != 1:
        return None
    statement = body[0]
    expression: ast.AST | None = None
    if isinstance(statement, ast.Return) and statement.value is not None:
        expression = statement.value
    elif isinstance(statement, ast.Expr):
        expression = statement.value
    if expression is None:
        return None
    return _delegation_for_expression(expression, imports, module_name)


def _delegation_for_expression(
    expression: ast.AST,
    imports: dict[str, str],
    module_name: str,
) -> FacadeDelegation | None:
    expression_text = _render_expr(expression)
    if not expression_text:
        return None
    if isinstance(expression, ast.Call):
        return _delegation_for_call(expression, expression_text, imports, module_name)
    if isinstance(expression, ast.Attribute):
        target = _resolve_reference(expression, imports, module_name)
        return FacadeDelegation(
            kind="attribute_read",
            expression=expression_text,
            target=target,
            target_group=_reference_group(target, module_name),
        )
    return None


def _delegation_for_call(
    expression: ast.Call,
    expression_text: str,
    imports: dict[str, str],
    module_name: str,
) -> FacadeDelegation | None:
    if isinstance(expression.func, ast.Attribute):
        receiver = expression.func.value
        kind = "attribute_call"
        target: str | None = None
        if isinstance(receiver, ast.Call):
            kind = "helper_call"
            helper_target = _resolve_reference(receiver.func, imports, module_name)
            target = f"{helper_target}.{expression.func.attr}" if helper_target else None
        elif _is_self_expression(receiver):
            kind = "self_call"
            receiver_target = _render_expr(receiver)
            target = f"{receiver_target}.{expression.func.attr}" if receiver_target else None
        else:
            receiver_target = _resolve_reference(receiver, imports, module_name)
            target = f"{receiver_target}.{expression.func.attr}" if receiver_target else None
        return FacadeDelegation(
            kind=kind,
            expression=expression_text,
            target=target,
            target_group=_reference_group(target, module_name),
        )
    if isinstance(expression.func, ast.Name):
        target = _resolve_reference(expression.func, imports, module_name)
        return FacadeDelegation(
            kind="function_call",
            expression=expression_text,
            target=target,
            target_group=_reference_group(target, module_name),
        )
    return None


def _class_surface_members(
    class_node: ast.ClassDef,
    *,
    include_private: bool,
    include_attributes: bool,
) -> list[_SurfaceMemberSpec]:
    members: list[_SurfaceMemberSpec] = []
    for statement in class_node.body:
        if isinstance(statement, ast.AnnAssign) and include_attributes and isinstance(statement.target, ast.Name):
            if include_private or not statement.target.id.startswith("_"):
                members.append(
                    _SurfaceMemberSpec(
                        name=statement.target.id,
                        kind="attribute",
                        start_line=statement.lineno,
                        end_line=_end_line(statement),
                        node=None,
                    )
                )
            continue
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not include_private and statement.name.startswith("_"):
            continue
        if _is_property(statement):
            kind = "property"
        elif isinstance(statement, ast.AsyncFunctionDef):
            kind = "async method" if _is_instance_method(statement) else "async callable"
        else:
            kind = "method" if _is_instance_method(statement) else "callable"
        members.append(
            _SurfaceMemberSpec(
                name=statement.name,
                kind=kind,
                start_line=statement.lineno,
                end_line=_end_line(statement),
                node=statement,
            )
        )
    return members


def _class_surface_member_names(
    file_path: Path,
    symbol: str,
    project_root: Path,
    *,
    include_private: bool,
) -> set[str]:
    source = file_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(file_path))
    class_node = _find_class_node(tree, symbol, file_path)
    return {
        member.name
        for member in _class_surface_members(
            class_node,
            include_private=include_private,
            include_attributes=True,
        )
    }


def _collect_feature_protocol_contracts(project_root: Path) -> tuple[ProtocolContract, ...]:
    features_root = project_root / "src" / "wrong_adventure" / "features"
    contracts: list[ProtocolContract] = []
    for feature_path in sorted(path for path in features_root.iterdir() if path.is_dir()):
        api_root = feature_path / "api"
        if api_root.is_dir():
            candidate_files = sorted(path for path in api_root.rglob("*.py") if path.is_file())
        else:
            public_path = feature_path / "public.py"
            candidate_files = [public_path] if public_path.exists() else []
        for file_path in candidate_files:
            source = file_path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source, filename=str(file_path))
            module_name = _module_name_for_file(file_path, project_root)
            imports = _import_aliases(tree, module_name)
            for statement in tree.body:
                if not isinstance(statement, ast.ClassDef):
                    continue
                resolved_bases = _resolved_class_bases(statement, imports, module_name)
                if not _is_protocol_class(statement, resolved_bases):
                    continue
                members = tuple(
                    member.name
                    for member in _class_surface_members(
                        statement,
                        include_private=False,
                        include_attributes=True,
                    )
                )
                contracts.append(
                    ProtocolContract(
                        feature=feature_path.name,
                        qualified_name=f"{module_name}.{statement.name}",
                        members=members,
                    )
                )
    return tuple(sorted(contracts, key=lambda item: (item.feature, item.qualified_name)))


def _resolved_class_bases(
    class_node: ast.ClassDef,
    imports: dict[str, str],
    module_name: str,
) -> tuple[str, ...]:
    resolved: set[str] = set()
    for base in class_node.bases:
        reference = _resolve_reference(base, imports, module_name) or _render_expr(base)
        if reference:
            resolved.add(reference)
    return tuple(sorted(resolved))


def _is_protocol_class(class_node: ast.ClassDef, resolved_bases: tuple[str, ...]) -> bool:
    if any(_is_protocol_reference(reference) for reference in resolved_bases):
        return True
    return any(isinstance(base, ast.Name) and base.id == "Protocol" for base in class_node.bases)


def _is_protocol_surface_class(
    class_name: str,
    is_protocol: bool,
    base_contracts: tuple[str, ...],
    member_audits: list[ProtocolMemberAudit],
    class_categories: list[str],
) -> bool:
    return bool(
        is_protocol
        or class_name.endswith("Bridge")
        or base_contracts
        or class_categories
        or any(member.replacement_contracts or member.delegation for member in member_audits)
    )


def _default_facade_file(project_root: Path) -> Path | None:
    candidate = project_root / "src" / "wrong_adventure" / "game" / "session.py"
    if candidate.exists():
        return candidate.resolve()
    return None


def _resolve_reference(expression: ast.AST, imports: dict[str, str], module_name: str) -> str | None:
    if isinstance(expression, ast.Name):
        if expression.id == "self":
            return "self"
        if expression.id in imports:
            return imports[expression.id]
        if hasattr(builtins, expression.id):
            return f"builtins.{expression.id}"
        return f"{module_name}.{expression.id}"
    if isinstance(expression, ast.Attribute):
        parent = _resolve_reference(expression.value, imports, module_name)
        if parent is None:
            parent = _render_expr(expression.value)
        if not parent:
            return expression.attr
        return f"{parent}.{expression.attr}"
    return None


def _reference_group(reference: str | None, module_name: str) -> str:
    if reference is None:
        return "unresolved"
    if reference.startswith("self"):
        return "self"
    if ".features." in reference and ".public" in reference:
        return "feature_public"
    if reference.startswith(f"{module_name}."):
        return "same_module"
    module_package, _, _ = module_name.rpartition(".")
    if module_package and reference.startswith(f"{module_package}."):
        return "same_package"
    if reference.startswith("wrong_adventure."):
        return "project_import"
    return "external"


def _sorted_layer_counts(call_sites: tuple[FacadeCallSite, ...]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = defaultdict(int)
    for call_site in call_sites:
        counts[call_site.layer] += 1
    return tuple(sorted(counts.items()))


def _method_categories(
    call_sites: tuple[FacadeCallSite, ...],
    delegation: FacadeDelegation | None,
) -> tuple[str, ...]:
    categories: list[str] = []
    if delegation is not None:
        categories.append("wrapper")
        if delegation.target_group not in {"self", "unresolved"}:
            categories.append(f"wrapper_to_{delegation.target_group}")
    production_layers = {call_site.layer for call_site in call_sites if call_site.layer != "tests"}
    if not call_sites:
        categories.append("no_callers")
    elif not production_layers:
        categories.append("test_only")
    elif production_layers == {"presentation"}:
        categories.append("presentation_only")
    if any(call_site.access_kind == "attribute" for call_site in call_sites):
        categories.append("attribute_reads")
    return tuple(categories)


def _layer_name(file_path: Path, project_root: Path) -> str:
    try:
        relative = file_path.relative_to(project_root)
    except ValueError:
        relative = file_path
    parts = relative.parts
    if not parts:
        return "other"
    if parts[0] == "tests":
        return "tests"
    if parts[0] == "tools":
        return "tools"
    if parts[0] == "src" and len(parts) >= 4:
        return parts[2]
    return parts[0]


def _render_layer_counts(layer_counts: tuple[tuple[str, int], ...]) -> str:
    if not layer_counts:
        return "none"
    return ",".join(f"{layer}={count}" for layer, count in layer_counts)


def _is_instance_method(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if not function_node.decorator_list:
        return True
    for decorator in function_node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "staticmethod":
            return False
    return True


def _is_property(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(isinstance(decorator, ast.Name) and decorator.id == "property" for decorator in function_node.decorator_list)


def _infer_self_assignment(statement: ast.Assign) -> tuple[str, str] | None:
    if len(statement.targets) != 1 or not _is_self_attribute(statement.targets[0]):
        return None
    field_name = statement.targets[0].attr
    annotation = _inferred_type_from_value(statement.value)
    if annotation is None:
        return None
    return field_name, annotation


def _inferred_type_from_value(value: ast.AST) -> str | None:
    if isinstance(value, ast.Call):
        return _render_expr(value.func)
    return None


def _is_self_attribute(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and isinstance(node.attr, str)
    )


def _is_self_expression(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "self"
    if isinstance(node, ast.Attribute):
        return _is_self_expression(node.value)
    if isinstance(node, ast.Call):
        return _is_self_expression(node.func)
    return False


def _is_protocol_reference(reference: str) -> bool:
    return reference == "typing.Protocol" or reference.endswith(".Protocol") or reference == "Protocol"


def _import_aliases(tree: ast.Module, module_name: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                key = alias.asname or alias.name.rsplit(".", 1)[-1]
                aliases[key] = alias.name
        elif isinstance(statement, ast.ImportFrom):
            module = _resolve_imported_module(module_name, statement.module, statement.level)
            for alias in statement.names:
                if alias.name == "*":
                    continue
                key = alias.asname or alias.name
                aliases[key] = f"{module}.{alias.name}" if module else alias.name
    return aliases


def _resolve_imported_module(module_name: str, imported_module: str | None, level: int) -> str:
    if level <= 0:
        return imported_module or ""
    parts = module_name.split(".")
    if parts:
        parts = parts[:-1]
    keep = max(0, len(parts) - (level - 1))
    prefix = parts[:keep]
    if imported_module:
        prefix.extend(imported_module.split("."))
    return ".".join(prefix)


def _collect_python_files(target_path: Path) -> list[Path]:
    if target_path.is_file():
        return [target_path]
    return sorted(
        file_path
        for file_path in target_path.rglob("*.py")
        if "__pycache__" not in file_path.parts
    )


def _module_name_for_file(file_path: Path, project_root: Path) -> str:
    src_root = project_root / "src"
    if file_path.is_relative_to(src_root):
        relative = file_path.relative_to(src_root)
    elif file_path.is_relative_to(project_root):
        relative = file_path.relative_to(project_root)
    else:
        relative = file_path
    parts = list(relative.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = Path(parts[-1]).stem
    return ".".join(parts)


def _render_node(node: CodeMapNode, depth: int) -> list[str]:
    indent = "  " * depth
    lines = [f"{indent}{node.kind} {node.name}: {node.start_line}-{node.end_line}"]
    for child in node.children:
        lines.extend(_render_node(child, depth + 1))
    return lines


def _display_path(file_path: Path, project_root: Path | None) -> str:
    if project_root is None:
        return str(file_path)
    try:
        return str(file_path.relative_to(project_root)).replace("\\", "/")
    except ValueError:
        return str(file_path)


def _type_reference_names(annotation: str) -> set[str]:
    try:
        node = ast.parse(annotation, mode="eval")
    except SyntaxError:
        return {annotation}
    names: set[str] = set()
    for inner in ast.walk(node):
        if isinstance(inner, ast.Name):
            names.add(inner.id)
        elif isinstance(inner, ast.Attribute):
            names.add(_render_expr(inner))
        elif isinstance(inner, ast.Constant) and isinstance(inner.value, str):
            names.update(_type_reference_names(inner.value))
    return names


def _render_expr(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = _render_expr(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return ""


def _alias_for_class(qualified_name: str) -> str:
    return "cls_" + "".join(character if character.isalnum() else "_" for character in qualified_name)


def _end_line(node: ast.AST) -> int:
    end_line = getattr(node, "end_lineno", None)
    if end_line is not None:
        return int(end_line)
    return int(getattr(node, "lineno"))
