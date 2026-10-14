"""CSV writing rules (section 12) and the items import parser."""

from __future__ import annotations

import pytest

from app.services.csv_format import CsvImportError, neutralize, parse_items_csv, write_csv


@pytest.mark.parametrize("cell", ["=1+1", "+33", "-2", "@SUM", "\tx", "\rx", "++", "--"])
def test_formula_like_cells_are_prefixed(cell: str) -> None:
    assert neutralize(cell) == "'" + cell


@pytest.mark.parametrize("cell", ["", "Texte", "1+1", "a=b", "'déjà"])
def test_ordinary_cells_are_unchanged(cell: str) -> None:
    assert neutralize(cell) == cell


def test_write_csv_uses_bom_semicolons_and_crlf() -> None:
    data = write_csv(["a", "b"], [["x;y", 'il dit "oui"'], ["=cmd", "é"]])
    assert data.startswith(b"\xef\xbb\xbf")
    assert data.decode("utf-8-sig") == 'a;b\r\n"x;y";"il dit ""oui"""\r\n\'=cmd;é\r\n'


def test_parse_accepts_commas_and_english_headers() -> None:
    groups = parse_items_csv("short_name,statement\nA,Première\nB,Seconde\n")
    assert [g.name for g in groups] == ["Général"]
    assert [i.short_name for i in groups[0].items] == ["A", "B"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "Le fichier est vide."),
        ("titre;texte\nA;B\n", "Colonnes attendues"),
        ("short_name;statement\n", "Aucun item"),
        ("short_name;statement\n" + "A;B\n" * 501, "500 items au maximum"),
        ("x" * 1_000_001, "trop volumineux"),
    ],
)
def test_parse_errors(text: str, message: str) -> None:
    with pytest.raises(CsvImportError, match=message):
        parse_items_csv(text)


def test_parse_rejects_too_many_groups() -> None:
    rows = "".join(f"G{n};I{n};S\n" for n in range(101))
    with pytest.raises(CsvImportError, match="100 groupes"):
        parse_items_csv("group;short_name;statement\n" + rows)


def test_the_documented_sample_file_imports() -> None:
    from pathlib import Path

    sample = Path(__file__).resolve().parents[3] / "docs" / "samples" / "items.csv"
    groups = parse_items_csv(sample.read_text(encoding="utf-8"))
    assert [g.name for g in groups] == ["Organisation", "Management", "Coopération"]
