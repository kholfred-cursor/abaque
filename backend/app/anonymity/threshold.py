"""Global k threshold (PROMPT_MVP section 11). Pure Python; sub-groups arrive in lot 2."""

from __future__ import annotations

DEFAULT_K = 3


class BelowThreshold(Exception):  # noqa: N818
    """The version has fewer than k ballots: individual outputs are refused."""


def check_global(ballot_count: int, k: int) -> None:
    """Refuse individual views and exports 2 and 3 when the version has fewer than k ballots."""
    if k < DEFAULT_K:
        raise ValueError("k is at least 3")
    if ballot_count < k:
        raise BelowThreshold
