# Refactor Phase 7: Material Mapping Probe

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Add a repeatable evidence report for the FBX import material path. The previous smoke harness proved RC can convert a sample FBX. This phase records whether the generated RC request and generated `.mtl` agree about material slots before the file reaches RC.

## What Changed

- Added `tools/material_mapping_report.py`.
- `tools/rc_smoke_test.py` now writes `<asset>.material_report.json` after running RC.
- The report captures:
  - RC request material order, name, physicalize value, and `sub_index`
  - generated `.mtl` sub-material slot order and names
  - `.mtl.cryasset` details such as `subMaterialCount`
  - expected RC output existence and byte size
  - per-material slot alignment checks
- Added tests for report parsing and smoke-report generation.

## Real Multi-Material Smoke

Command:

```powershell
uv run python -m tools.rc_smoke_test --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_materials" --asset-name "CubeA_material_probe" --materials "Default,Detail,collision_proxy"
```

Generated report:

```text
S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_materials\CubeA_material_probe.material_report.json
```

RC output:

```text
S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_materials\CubeA_material_probe.cgf
```

The `.cgf` was present and non-empty. In this run it was 3440 bytes.

## Observed Input Mapping

Request material entries:

```json
[
  {"order": 0, "name": "Default", "sub_index": 0, "physicalize": "no_collide"},
  {"order": 1, "name": "Detail", "sub_index": 1, "physicalize": "no_collide"},
  {"order": 2, "name": "collision_proxy", "sub_index": 2, "physicalize": "proxy_only"}
]
```

Generated MTL slots:

```json
[
  {"slot": 0, "name": "Default", "shader": "Illum", "surface_type": ""},
  {"slot": 1, "name": "Detail", "shader": "Illum", "surface_type": ""},
  {"slot": 2, "name": "collision_proxy", "shader": "Illum", "surface_type": ""}
]
```

The report marked all three slot checks as `slot_name_match` and `alignment.ok = true`.

## Important Boundary

This phase proves the converter's generated inputs are self-consistent:

```text
request.materials[].sub_index <-> .mtl SubMaterials child order
```

It does not yet prove that the final `.cgf` polygon material ids use those slots correctly. For that, the next phase needs one of:

- a CryEngine-aware CGF chunk reader,
- a small engine/editor-side inspection pass,
- or a controlled Blender-exported FBX with known face-to-material assignments and a readable post-RC validation path.

## Verification

Passed:

```powershell
uv run python -m pytest tests
uv run python -m compileall main.py model_processing output_formats utils tools tests
uv run python -m tools.rc_smoke_test --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_materials" --asset-name "CubeA_material_probe" --materials "Default,Detail,collision_proxy"
```

## Remaining Work

- Build or locate a CGF reader that can inspect material chunks and mesh face material ids.
- Generate a controlled FBX fixture from Blender with multiple actual material assignments, not only a multi-material request.
- Decide how `proxy_only` should be represented in `.mtl` attributes in addition to the RC request `physicalize` field.
- Add material report summaries to the PySide UI after the conversion runner is stable.
