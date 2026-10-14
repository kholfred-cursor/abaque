"""Identifying-data detection: e-mail, phone, proper names; sentence starts are not flagged."""

from __future__ import annotations

import pytest

from app.anonymity.detection import is_identifying
from app.anonymity.threshold import BelowThreshold, check_global


@pytest.mark.parametrize(
    "text",
    [
        "Écrivez-moi à jean.dupont@exemple.fr pour en parler",
        "contact : a+b@sub.domaine.co.uk",
        "Appelez le 06 12 34 56 78",
        "tel 06.12.34.56.78",
        "mon numéro 0612345678",
        "+33 6 12 34 56 78 de préférence",
        "joignable au +44 20 7946 0958",
        "Je pense que Jean Dupont a raison",
        "le service de Marie-Claire Lefèvre est débordé",
        "voir avec O'Neil Smith",
        "Bonne idée. Sinon Paul Martin pourrait aider",
    ],
)
def test_identifying_texts_are_flagged(text: str) -> None:
    assert is_identifying(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Mon Responsable est à l'écoute.",  # capitalized pair at the start of the text
        "Très bien. Mon Manager écoute.",  # ... and at the start of a sentence
        "La charge de travail est trop lourde depuis 2024",
        "Score 5 sur 5, rien à ajouter",
        "Réunion à 14h30, salle 12",
        "Le budget est de 120 000 euros",
        "un PDF et une API",  # acronyms are not title case
        "Bien, Marie.",  # single capitalized word
        "Paris, Lyon et Bordeaux",  # separated by punctuation
        "année 2025-2026",
    ],
)
def test_ordinary_texts_are_not_flagged(text: str) -> None:
    assert not is_identifying(text)


def test_global_threshold() -> None:
    check_global(3, 3)
    with pytest.raises(BelowThreshold):
        check_global(2, 3)
    with pytest.raises(BelowThreshold):
        check_global(4, 5)
    with pytest.raises(ValueError, match="at least 3"):
        check_global(10, 2)
