import ast
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script", sorted((ROOT / "tools").rglob("*.py")), ids=lambda p: p.name)
def test_tools_import_only_existing_voidtrace_names(script):
    for node in ast.walk(ast.parse(script.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("voidtrace"):
            module = importlib.import_module(node.module)
            for alias in node.names:
                if not hasattr(module, alias.name):
                    importlib.import_module(f"{node.module}.{alias.name}")  # a submodule, or it raises
