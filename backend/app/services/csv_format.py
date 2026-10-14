"""CSV writing and item import, shared by every CSV the application produces.

Writing (PROMPT_MVP section 12): UTF-8 with BOM, ';' separator, CRLF line endings, and
formula neutralisation (a cell starting with =, +, -, @, tab or CR is prefixed with ').
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence

from pydantic import ValidationError

from app.domain.content import (
    MAX_GROUPS_PER_VERSION,
    MAX_ITEMS_PER_VERSION,
    GroupInput,
    ItemInput,
)

BOM = "﻿"
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
DEFAULT_GROUP = "Général"
MAX_IMPORT_CHARS = 1_000_000

# Accepted header names (English canonical names, French aliases for spreadsheet users).
_COLUMNS: dict[str, tuple[str, ...]] = {
    "group": ("group", "groupe"),
    "short_name": ("short_name", "nom_court", "item"),
    "statement": ("statement", "affirmation", "enonce", "énoncé"),
}
ITEMS_HEADER = ("group", "short_name", "statement")


class CsvImportError(Exception):
    """Unreadable import, with a French message that names the faulty line."""


def neutralize(cell: str) -> str:
    return "'" + cell if cell.startswith(_FORMULA_PREFIXES) else cell


def write_csv(header: Sequence[str], rows: Iterable[Sequence[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(header)
    for row in rows:
        writer.writerow([neutralize(cell) for cell in row])
    return (BOM + buffer.getvalue()).encode("utf-8")


def items_csv(groups: Sequence[GroupInput]) -> bytes:
    return write_csv(
        ITEMS_HEADER,
        ((group.name, item.short_name, item.statement) for group in groups for item in group.items),
    )


def _unneutralize(cell: str) -> str:
    """Undo our own export prefix so an exported file re-imports unchanged."""
    if cell.startswith("'") and cell[1:2] in _FORMULA_PREFIXES:
        return cell[1:]
    return cell


def parse_items_csv(text: str) -> list[GroupInput]:
    """Parse an items file into groups in order of first appearance."""
    if len(text) > MAX_IMPORT_CHARS:
        raise CsvImportError("Fichier trop volumineux (1 Mo au maximum).")
    text = text.removeprefix(BOM)
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise CsvImportError("Le fichier est vide.")
    delimiter = ";" if lines[0].count(";") >= lines[0].count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = [cell.strip().lower() for cell in next(reader)]
    positions: dict[str, int] = {}
    for column, aliases in _COLUMNS.items():
        for index, name in enumerate(header):
            if name in aliases:
                positions[column] = index
                break
    missing = [c for c in ("short_name", "statement") if c not in positions]
    if missing:
        raise CsvImportError("Colonnes attendues : group ; short_name ; statement (ligne 1).")

    groups: dict[str, list[ItemInput]] = {}
    count = 0
    for line_number, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue

        def cell(column: str, row: list[str] = row) -> str:
            index = positions.get(column)
            if index is None or index >= len(row):
                return ""
            return _unneutralize(row[index].strip())

        group_name = cell("group") or DEFAULT_GROUP
        try:
            item = ItemInput(short_name=cell("short_name"), statement=cell("statement"))
            GroupInput(name=group_name)
        except ValidationError as exc:
            raise CsvImportError(
                f"Ligne {line_number} : nom court (1 à 50 caractères), affirmation "
                f"(1 à 2000 caractères) et groupe (200 caractères au plus) sont requis."
            ) from exc
        groups.setdefault(group_name, []).append(item)
        count += 1
        if count > MAX_ITEMS_PER_VERSION:
            raise CsvImportError(f"{MAX_ITEMS_PER_VERSION} items au maximum.")
    if count == 0:
        raise CsvImportError("Aucun item trouvé dans le fichier.")
    if len(groups) > MAX_GROUPS_PER_VERSION:
        raise CsvImportError(f"{MAX_GROUPS_PER_VERSION} groupes au maximum.")
    return [GroupInput(name=name, items=items) for name, items in groups.items()]
