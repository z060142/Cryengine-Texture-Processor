#!/usr/bin/env python3
"""Generate the tiny deterministic PNG set used by the T-012 gate smoke."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    Image.new("RGB", (2, 2), (128, 96, 64)).save(args.out / "Smoke_diff.png")
    Image.new("RGB", (2, 2), (128, 128, 255)).save(args.out / "smoke_normal.png")
    Image.new("L", (2, 2), 160).save(args.out / "SMOKE_roughness.png")
    Image.new("L", (2, 2), 32).save(args.out / "Smoke_height.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
