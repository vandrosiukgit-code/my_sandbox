import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_durak_domain_does_not_import_visual_runtime_modules(self):
        forbidden_roots = {"pygame", "activities", "group", "game_screen.frame", "actions"}
        offenders = {}

        for path in (PROJECT_ROOT / "core" / "durak").glob("*.py"):
            imports = imported_modules(path)
            forbidden = sorted(
                module
                for module in imports
                if module in forbidden_roots or module.split(".", 1)[0] in forbidden_roots
            )
            if forbidden:
                offenders[str(path.relative_to(PROJECT_ROOT))] = forbidden

        self.assertEqual(offenders, {})

    def test_activities_do_not_import_isolated_durak_controller(self):
        offenders = {}

        for path in (PROJECT_ROOT / "activities").glob("*.py"):
            imports = imported_modules(path)
            forbidden = sorted(module for module in imports if module.startswith("core.durak"))
            if forbidden:
                offenders[str(path.relative_to(PROJECT_ROOT))] = forbidden

        self.assertEqual(offenders, {})


if __name__ == "__main__":
    unittest.main()
