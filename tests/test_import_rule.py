"""The flow library imports neither the server nor the command line, so a flow
can run anywhere the library is installed (ADR 0002)."""

import ast
from pathlib import Path

import fcon_sdk

FORBIDDEN = ("fcon_server", "fcon_cli")


def imported_modules(source: Path) -> set[str]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def test_the_flow_library_imports_neither_the_server_nor_the_command_line():
    library = Path(fcon_sdk.__file__).parent

    found = {
        f"{source.relative_to(library)}: {name}"
        for source in library.rglob("*.py")
        for name in imported_modules(source)
        if name.split(".")[0] in FORBIDDEN
    }

    assert not found, f"fcon_sdk imports {sorted(found)}"
