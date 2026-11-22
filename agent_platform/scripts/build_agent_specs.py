"""Build deterministic, deployment-neutral Sof~IA agent artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from artifact_builder import ValidationError, write_artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    platform_root = Path(__file__).resolve().parents[1]
    try:
        destination = write_artifact(platform_root, args.output)
    except ValidationError as error:
        print(error, file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
