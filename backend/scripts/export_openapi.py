#!/usr/bin/env python3
"""Export the OpenAPI schema to stdout (used by the CI `contract` job).

Usage (from backend/):
    uv run python scripts/export_openapi.py > ../openapi.json

Requires app.main.create_app (delivered in lot 0, block 3b part 2/2).
Output is deterministic: sorted keys, 2-space indent, trailing newline.
"""

from __future__ import annotations

import json
import sys

from app.main import create_app


def main() -> None:
    app = create_app()
    sys.stdout.write(json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
