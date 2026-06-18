# Refactor Phase 30: MTL Document Builder

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Make CryEngine `.mtl` generation easier to verify and replace with real RC/CryEngine rules.

Before this phase, `output_formats.mtl_exporter.export_mtl` did all of this in one large block:

```text
slot assignment -> gap filling -> XML attributes -> texture map names -> GenMask -> PublicParams -> file write
```

That made the current guessed values hard to test and risky to change.

## What Changed

`output_formats.mtl_exporter` now exposes pure builder helpers:

```text
build_mtl_material_slots(materials_data, existing_submaterial_names=None)
build_mtl_document(materials_data, model_output_dir, existing_submaterial_names=None)
```

The exporter now delegates to those helpers and keeps the public `export_mtl(...)` entry point.

The MTL rules that used to be embedded inside `export_mtl` are now named constants or helper blocks:

- `CRYENGINE_MAP_TYPES`
- `SUB_MATERIAL_DEFAULT_ATTRS`
- `BASE_PUBLIC_PARAMS`
- GenMask bit constants
- alpha texture detection
- texture `<Texture Map=... File=...>` emission
- shader mask / `PublicParams` emission

## Behavior Preserved

The exporter still:

- preserves known FBX/manifest `sub_index` slots
- fills missing slots with `unassigned`
- writes a default material for empty input
- maps internal `normal` textures to CryEngine `Bumpmap`
- maps `displacement` textures to `Heightmap`
- maps alpha/opacity textures to `Opacity` and enables `AlphaTest`
- emits the same current guessed GenMask/StringGenMask values
- writes `.mtl.cryasset` after `.mtl`

## Small Fixes

Texture type checks are now case-insensitive for shader masks and public params, matching the texture map emission path.

The `.mtl.cryasset` writer now receives the actual material slots emitted by the `.mtl` document builder. Empty input therefore produces a default `.mtl` material and a matching `subMaterialCount = 1`.

## Rule

This phase does not claim that the current GenMask, shader, public parameter, or material template values are CryEngine-correct.

It only makes the current behavior inspectable and replaceable:

```text
current guessed MTL rules -> named builder helpers -> targeted tests -> future CE/RC evidence replacement
```

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_mtl_exporter.py tests\test_rc_smoke_test.py tests\test_material_mapping_report.py tests\test_material_texture_resolver.py
```

New tests cover:

- expanded material slot tables
- default material creation
- texture map names and relative paths
- case-insensitive shader mask input
- displacement tessellation public params
- `.mtl.cryasset` default material count

## Remaining Work

- Compare generated `.mtl` against real CryEngine Material Editor output.
- Replace guessed GenMask/StringGenMask values with evidence-backed constants.
- Decide how PBR-derived material fields should map to CE shader params.
- Add a report that compares generated `.mtl` fields against an expected schema.
