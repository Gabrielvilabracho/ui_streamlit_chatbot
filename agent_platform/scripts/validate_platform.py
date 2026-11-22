"""Validate editable Sof~IA agent sources without generating an artifact."""

from __future__ import annotations

import sys
from pathlib import Path

from artifact_builder import ValidationError, build_spec


def main() -> int:
    try:
        build_spec(Path(__file__).resolve().parents[1])
    except ValidationError as error:
        print(error, file=sys.stderr)
        return 1
    print("agent platform configuration is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
