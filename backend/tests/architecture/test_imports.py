"""AST-only import-boundary tests for database and anonymity dependencies."""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).parents[2] / "app"
RESTRICTED = {"entitlements", "vote_engine", "anonymity", "domain"}
BALLOT_READER_ALLOWED = {
    "app/anonymity",
    "app/services/restitution",
    "app/services/export",
    "app/domain/ports.py",
}


def _imports(path: Path) -> list[str]:
    return _imports_from_source(path.read_text(encoding="utf-8"))


def _imports_from_source(source: str) -> list[str]:
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        # Also catch `ports.BallotReaderPort` reached through a module import.
        if isinstance(node, ast.Attribute) and node.attr == "BallotReaderPort":
            names.append("__ballot_reader__")
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
            if any(alias.name == "BallotReaderPort" for alias in node.names):
                names.append("__ballot_reader__")
    return names


def test_database_imports_are_confined_to_db_and_repositories() -> None:
    for path in APP.rglob("*.py"):
        imports = _imports(path)
        relative = path.relative_to(APP).as_posix()
        for name in imports:
            assert not name.startswith("motor")
            if name.startswith(("pymongo", "bson")):
                assert relative.startswith(("db/", "repositories/"))


def test_pure_domains_do_not_depend_on_database_web_or_repositories() -> None:
    for directory in RESTRICTED:
        for path in (APP / directory).rglob("*.py"):
            imports = _imports(path)
            assert not any(
                name.startswith(("pymongo", "bson", "fastapi", "app.repositories"))
                for name in imports
            )


def test_ballot_reader_port_is_imported_only_by_authorized_modules() -> None:
    for path in APP.rglob("*.py"):
        if "__ballot_reader__" in _imports(path):
            relative = path.relative_to(APP).as_posix()
            assert any(
                relative == allowed.removeprefix("app/")
                or relative.startswith(allowed.removeprefix("app/") + "/")
                for allowed in BALLOT_READER_ALLOWED
            )


def test_scanner_sees_the_code_and_detects_violations() -> None:
    """Guard against vacuous passes: the scan covers files and flags known-bad sources."""
    assert len(list(APP.rglob("*.py"))) > 30
    assert "pymongo" in _imports_from_source("import pymongo")
    assert "bson.objectid" in _imports_from_source("from bson.objectid import ObjectId")
    assert "__ballot_reader__" in _imports_from_source(
        "from app.domain.ports import BallotReaderPort"
    )
    assert "__ballot_reader__" in _imports_from_source(
        "from app.domain import ports\nx = ports.BallotReaderPort"
    )
