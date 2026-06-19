# Asset Flow Acceptance Baseline

Date: 2026-06-20

## Purpose

This is the current practical acceptance snapshot for the rough CryEngine asset
conversion flow. It is meant to prevent re-reading the whole codebase or the
whole conversation history before continuing development.

The target is not a perfect importer. The target is a usable path where:

- raw texture inputs can produce RC-acceptable CryEngine texture outputs;
- FBX inputs can be copied to an ASCII work directory and converted by `rc.exe`
  into `.cgf`;
- generated JSON, MTL, material slots, material names, and processed texture
  references agree well enough to build user tooling;
- generated MTL values are checked by the CryEngine MTL schema gate and printed
  into validation reports.

## Strongest Current Evidence

### Texture-Backed Batch

Report:

```text
S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\texture_backed_only_batch_report.json
S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\texture_backed_only_batch_report.md
```

Command shape:

```powershell
uv run python -m tools.asset_flow_spec_builder `
  "D:\DATA\00_DATA2\Art Assets\Models\Unreal Engine\polypixel\PostApocalypticWorld\Models\FBX" `
  --obj-mtl-root "D:\DATA\00_DATA2\Art Assets\Models\Unreal Engine\polypixel\PostApocalypticWorld\Models\OBJ" `
  --include-texture-process `
  --texture-backed-only `
  --max-textures-per-case 2 `
  --output "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\texture_backed_only_batch_spec.json" `
  --work-root "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\texture_backed_only_batch" `
  --limit 3 `
  --max-mb 2
```

Observed result:

```text
ok: True
case_count: 6
ok_count: 6
failed_count: 0
```

Coverage:

```text
raw_textures_found: pass=3 fail=0 na=0
texture_processing_started: pass=3 fail=0 na=0
texture_format_ok: pass=6 fail=0 na=0
manifest_generated: pass=3 fail=0 na=0
model_format_ok: pass=3 fail=0 na=0
material_slots_ok: pass=3 fail=0 na=0
mtl_format_ok: pass=3 fail=0 na=0
material_texture_ok: pass=3 fail=0 na=0
```

Validated texture-backed FBX cases:

```text
Ivy_Climb_d128b427
Ivy_Medium_94ee8462
Ivy_Large_524ced31
```

Observed MTL texture links:

```text
Ivy_small_mat -> Ivy_Small_diff.tif, Ivy_Small_ddn.tif, Ivy_Small_spec.tif
Ivy_medium_mat -> Ivy_Medium_diff.tif, Ivy_Medium_ddn.tif, Ivy_Medium_spec.tif
Ivy_large_mat -> Ivy_Large_diff.tif, Ivy_Large_ddn.tif, Ivy_Large_spec.tif
```

This is the best current proof that the rough end-to-end chain can work:
OBJ MTL evidence -> raw texture process -> CryEngine texture outputs -> MTL
texture links -> RC JSON -> `.cgf`.

### Mixed Batch

Report:

```text
S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\auto_texture_batch_limited_report.json
S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\auto_texture_batch_limited_report.md
```

Observed result:

```text
ok: True
case_count: 10
ok_count: 10
failed_count: 0
```

Coverage shows the difference between model-only and texture-backed cases:

```text
manifest_generated: pass=8 fail=0 na=0
model_format_ok: pass=8 fail=0 na=0
material_slots_ok: pass=8 fail=0 na=0
mtl_format_ok: pass=8 fail=0 na=0
texture_format_ok: pass=4 fail=0 na=6
material_texture_ok: pass=2 fail=0 na=6
raw_textures_found: pass=2 fail=0 na=0
texture_processing_started: pass=2 fail=0 na=0
```

Use this mode when broad RC stability matters. Use `--texture-backed-only`
when material-texture coverage matters.

### Small FBX Batch

Report:

```text
S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\small_fbx_batch_report.json
S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\small_fbx_batch_report.md
```

Observed result:

```text
ok: True
case_count: 5
ok_count: 5
failed_count: 0
```

This batch includes FBX sources under `D:\DATA\3D模型`. The validator copies
FBX files, manifests, MTL, and RC JSON into ASCII work directories before RC
runs. This is the current guard against RC sensitivity to Chinese paths.

## Current Rules Worth Preserving

- Generated Blender material manifests default to the ASCII case work
  directory, not next to the source FBX.
- The generated MTL always includes the trailing `<unassigned>` material because
  CryEngine models may expose that slot and it should be treated as expected.
- `tif` and `dds` are both accepted CryEngine texture output extensions by the
  texture output gates.
- OBJ `.mtl` evidence is a fallback for material-to-texture mapping when FBX
  texture refs are weak or missing.
- `--max-textures-per-case` keeps automatic raw texture processing bounded.
- `--texture-backed-only` should be used for batches intended to exercise
  `material_texture_ok`.

## Known Limits

- OBJ `.mtl` matching is practical, not exhaustive. It uses FBX stem hints and
  same-base texture expansion such as `_a` -> `_n`, `_normal`, `_s`, `_spec`.
- Default spec generation does not prove every model has correct artistic
  material assignment; it proves the current rule chain is internally
  consistent and accepted by the gates.
- Some reports created before `check_counts` existed do not include coverage in
  JSON. Re-run the validator if current coverage fields are needed.
- The UI is not the source of truth for this baseline yet. The CLI validator is
  the strongest verified path.

## Useful Commands

Focused tests:

```powershell
uv run pytest tests/test_asset_flow_spec_builder.py tests/test_asset_flow_validator.py -q
```

Broader related tests:

```powershell
uv run pytest tests/test_asset_flow_spec_builder.py tests/test_asset_flow_validator.py tests/test_obj_mtl_report.py tests/test_rc_smoke_test.py tests/test_material_texture_resolver.py -q
```
