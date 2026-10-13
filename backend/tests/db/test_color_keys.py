"""The validators' colour keys match the shared design scale, in order.

docs/design/scale.json is the single source shared with the frontend (scale.ts is
checked against it on that side), so the two never import each other's code.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.db.schemas._patterns import COLOR_KEYS

SCALE_JSON = Path(__file__).resolve().parents[3] / "docs" / "design" / "scale.json"


def test_color_keys_match_the_design_scale() -> None:
    scale = json.loads(SCALE_JSON.read_text(encoding="utf-8"))["scale"]
    assert [color["key"] for color in scale] == COLOR_KEYS
