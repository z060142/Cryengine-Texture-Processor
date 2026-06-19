# Phase 110 - Dev Example MTL Flow

## What was run

The direct user-flow command was run against the checked-in example materials:

```powershell
uv run python tools/mtl_schema_report.py dev_example --output docs/phase110_dev_example_mtl_schema_report.json
```

This originally failed because direct script execution from `tools/*.py` did not
put the repository root on `sys.path`. Running the same tool as a module worked,
but that is too fragile for quick asset-pipeline smoke work.

## Tooling fix

Added `tools/_repo_path.py` and bootstrapped the repo root in the tools that
import repo-local packages.

The direct script path now works for the MTL schema report and related RC/MTL
probe tools.

## Dev example result

Input:

- `dev_example/test.mtl`
- `dev_example/test_2.mtl`
- `dev_example/cliff_side1.mtl`

Summary:

- files: 3
- materials: 17
- texture entries: 21
- Bumpmap entries: 6

Texture suffix statuses after Phase 109:

- `matches_expected_suffix`: 11
- `matches_accepted_alias_suffix`: 6
- `mismatch_expected_suffix`: 3
- `no_source_backed_suffix`: 1

The six Bumpmap `_ddna` entries are now correctly classified as accepted alias
matches instead of suffix mismatches.

## Remaining real mismatches in dev examples

These still look like genuine material/texture assignment issues:

- `cliff_side1.mtl`
  - `Map="Emittance"` uses `cliff_side_emissive.dds`
  - expected CE suffix is `_em`
- `cliff_side1.mtl`, material `cliff_bush`
  - `Map="Specular"` uses `./model/rock_face_01_diff.dds`
  - expected CE suffix is `_spec`
- `cliff_side1.mtl`, material `cliff_bush`
  - `Map="Heightmap"` uses `./model/rock_face_01_diff.dds`
  - expected CE suffix is `_displ`

`Opacity` currently reports `no_source_backed_suffix` because the current CE
suffix table does not assign a source-backed filename suffix to `Opacity`.

## Why this matters

This rough flow confirms that `_ddna` alias handling removes real false
positives from example materials, leaving a smaller set of warnings that are
more likely to represent actual authoring or mapping problems.

For Blender plugin work, the diagnostics should treat:

- `_ddna` Bumpmap as valid normal-alpha output
- `_diff` reused as Specular/Heightmap as suspicious unless intentionally
  documented by a CE sample
- `_emissive` vs `_em` as an unresolved naming-policy question

## Verification

- `uv run python tools/mtl_schema_report.py dev_example --output docs/phase110_dev_example_mtl_schema_report.json`
