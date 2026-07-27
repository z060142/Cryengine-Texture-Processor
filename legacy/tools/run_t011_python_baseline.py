#!/usr/bin/env python
"""Run the legacy Python texture batch for T-011 pixel comparisons."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from core.batch_processor import BatchProcessor
from core.texture_manager import TextureGroup


class _SingleGroupManager:
    def __init__(self, group: TextureGroup) -> None:
        self._group = group

    def get_all_groups(self) -> list[TextureGroup]:
        return [self._group]


def _source(path: Path, texture_type: str) -> dict[str, object]:
    return {
        "path": str(path),
        "abs_path": str(path.resolve()),
        "filename": path.name,
        "type": texture_type,
        "base_name": "KB3D_ENC_AtlasA",
        "is_unknown": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--diff-format",
        choices=("albedo", "diffuse_ao"),
        default="albedo",
    )
    parser.add_argument("--process-metallic", action="store_true")
    parser.add_argument(
        "--outputs",
        choices=("all", "diff"),
        default="all",
    )
    args = parser.parse_args()

    fixture_paths = {
        "diffuse": args.fixtures / "KB3D_ENC_AtlasA_basecolor.png",
        "normal": args.fixtures / "KB3D_ENC_AtlasA_normal.png",
        "roughness": args.fixtures / "KB3D_ENC_AtlasA_roughness.png",
        "displacement": args.fixtures / "KB3D_ENC_AtlasA_height.png",
        "metallic": args.fixtures / "KB3D_ENC_AtlasA_metallic.png",
        "ao": args.fixtures / "KB3D_ENC_AtlasA_ao.png",
        "alpha": args.fixtures / "KB3D_ENC_AtlasA_opacity.png",
    }
    missing = [str(path) for path in fixture_paths.values() if not path.is_file()]
    if missing:
        parser.error(f"missing T-011 fixtures: {missing}")

    group = TextureGroup("KB3D_ENC_AtlasA")
    for texture_type, path in fixture_paths.items():
        group.add_texture(texture_type, _source(path, texture_type))
    if args.outputs == "all":
        group.add_texture(
            "emissive",
            _source(fixture_paths["diffuse"], "emissive"),
        )
        group.add_texture(
            "sss",
            _source(fixture_paths["diffuse"], "sss"),
        )

    args.output.mkdir(parents=True, exist_ok=True)
    enabled = args.outputs == "all"
    settings = {
        "output_resolution": "original",
        "diff_format": args.diff_format,
        "process_metallic": args.process_metallic,
        "normal_from_height_strength": 10.0,
        "normal_flip_green": False,
        "normalize_height": False,
        "generate_missing_spec": True,
        "generate_missing_emissive": False,
        "generate_missing_sss": False,
        "generate_sss_from_diffuse": False,
        "emissive_brightness": 1.0,
        "sss_intensity": 1.0,
        "texture_types": {
            "diff": True,
            "spec": enabled,
            "ddna": enabled,
            "displ": enabled,
            "emissive": enabled,
            "sss": enabled,
        },
    }

    processor = BatchProcessor(_SingleGroupManager(group))
    processor.set_output_dir(str(args.output))
    processor.set_settings(settings)
    if not processor.process_all_groups():
        raise RuntimeError("legacy BatchProcessor refused to start")
    processor.processing_thread.join()

    outputs = sorted(path for path in args.output.glob("*.tif"))
    expected_count = 6 if enabled else 1
    if len(outputs) != expected_count:
        raise RuntimeError(
            f"legacy batch produced {len(outputs)} TIFF files, expected {expected_count}"
        )

    print(
        json.dumps(
            {
                "base_name": group.base_name,
                "diff_format": args.diff_format,
                "process_metallic": args.process_metallic,
                "outputs": [str(path.resolve()) for path in outputs],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
