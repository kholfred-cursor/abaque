"""Shared regex patterns for $jsonSchema validators."""

from __future__ import annotations

UUID_V4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
DAY = r"^\d{4}-\d{2}-\d{2}$"
MONTH = r"^\d{4}-\d{2}$"
SHA256_HEX = r"^[0-9a-f]{64}$"
KEY_ID = r"^[0-9a-f]{16}$"
ARGON2ID = r"^\$argon2id\$"
COLOR_KEYS = ["++", "+", "~", "-", "--"]
