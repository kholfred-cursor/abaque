"""Detection of identifying data in free texts (PROMPT_MVP section 11). Pure Python.

A text that matches is stored as ``flagged``: excluded from every view and export until
an animator validates it. False positives only cost a moderation step; a false negative
could expose someone, so the rules lean towards flagging.
"""

from __future__ import annotations

import itertools
import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.UNICODE)
# French numbers (06 12 34 56 78, 06.12.34.56.78, +33 6 12 34 56 78, 0612345678) and any
# international number (+ followed by at least 8 digits, spaces/dots/dashes allowed).
_PHONE_FR = re.compile(r"(?<!\d)(?:\+33[\s.-]?|0033[\s.-]?|0)[1-9](?:[\s.-]?\d{2}){4}(?!\d)")
_PHONE_INTL = re.compile(r"(?<![\w+])\+\d(?:[\s.-]?\d){7,14}(?!\d)")
_APOSTROPHES = "'\u2019"  # straight and typographic apostrophes
_WORD = re.compile(r"[^\W\d_]+(?:[-" + _APOSTROPHES + r"][^\W\d_]+)*", re.UNICODE)
_SENTENCE_END = re.compile(r"[.!?…:;\n]\s*$")


def _is_capitalized(word: str) -> bool:
    """Title case: an upper-case initial followed by at least one lower-case letter."""
    return word[0].isupper() and any(char.islower() for char in word[1:])


def _has_proper_name_pair(text: str) -> bool:
    """Two consecutive capitalized words, the first one not starting a sentence."""
    words = list(_WORD.finditer(text))
    for current, following in itertools.pairwise(words):
        if not (_is_capitalized(current.group()) and _is_capitalized(following.group())):
            continue
        between = text[current.end() : following.start()]
        if between.strip() or "\n" in between:
            continue  # separated by punctuation: not a name pair
        before = text[: current.start()]
        if before.strip() == "" or _SENTENCE_END.search(before):
            continue  # "Mon Responsable..." at the start of a sentence
        return True
    return False


def is_identifying(text: str) -> bool:
    return bool(
        _EMAIL.search(text)
        or _PHONE_FR.search(text)
        or _PHONE_INTL.search(text)
        or _has_proper_name_pair(text)
    )
