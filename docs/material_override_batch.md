# Material Override Batch

## Why

The converter needed a batch path for material state that is already known from
CryEngine `.mtl` evidence. Guessing shader families and shader-specific params
inside the exporter does not scale, especially for `Glass`,
`Multilayeredmaterials`, and the permanent trailing `<unassigned>` slot.

This batch adds an explicit override channel:

- extract per-material CryEngine state from a reference `.mtl`
- feed that override JSON into model/MTL export
- preserve shader, GenMask, StringGenMask, material attrs, and PublicParams
- keep texture resolution and RC material slot assignment separate

## Files

- `tools/mtl_override_extractor.py`
- `tools/rc_smoke_test.py`
- `tools/rc_export_gate.py`
- `output_formats/mtl_exporter.py`
- `model_processing/material_texture_resolver.py`
- `tools/mtl_material_state_compare.py`
- `tools/mtl_schema_report.py`
- `docs/car_native_material_overrides.json`
- `docs/car_material_override_mtl_schema_report.json`
- `docs/car_material_state_compare.json`
- `docs/car_rc_smoke_mtl_schema_gate.json`
- `docs/car_direct_rc_export_material_report.json`
- `docs/car_direct_rc_export_mtl_schema_gate.json`
- `docs/car_direct_rc_export_texture_output_gate.json`

## Override Shape

`tools.mtl_override_extractor` emits:

```json
{
  "schema": "cryengine_material_overrides.v1",
  "source_mtl": "absolute reference mtl path",
  "material_overrides": {
    "MaterialName": {
      "cryengine_material": {
        "Shader": "Illum",
        "GenMask": "...",
        "StringGenMask": "...",
        "MtlFlags": "...",
        "PublicParams": {}
      }
    }
  }
}
```

The exporter also accepts the same material state directly on a material dict via
`cryengine_material`, `ce_material`, or `mtl_overrides`.

Important behavior:

- explicit empty `StringGenMask=""` is preserved
- explicit `PublicParams` replace the exporter defaults
- the generated trailing `<unassigned>` placeholder can receive overrides by name
- RC request materials are not polluted by the placeholder override

## Car Batch

Reference extraction:

```powershell
uv run python -m tools.mtl_override_extractor "S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.mtl" --output docs\car_native_material_overrides.json
```

RC flow:

```powershell
$phase = 'S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase127_material_overrides'
$overrideJson = 'S:\Crytek\crytek\Stripped to the bone\Cryengine-Texture-Processor\docs\car_native_material_overrides.json'

uv run python -m tools.rc_smoke_test --rc "S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe" --fbx (Join-Path $phase 'kb3d_citycarsessentialssedan-native.fbx') --work-dir (Join-Path $phase 'rc_work') --asset-name kb3d_citycarsessentialssedan-native --materials-from-manifest --material-overrides $overrideJson --reference-mtl "S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.mtl" --material-state-compare-output docs\car_material_state_compare.json --mtl-schema-gate-output docs\car_rc_smoke_mtl_schema_gate.json --texture-output-dir "S:\Crytek\crytek\Stripped to the bone\example\car" --texture-output-format "dds,tif" --texture-output-gate-output docs\car_rc_smoke_texture_output_gate.json

uv run python -m tools.mtl_schema_report "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase127_material_overrides\rc_work\kb3d_citycarsessentialssedan-native.mtl" --output docs\car_material_override_mtl_schema_report.json
```

Native and generated MTL now match on the high-value material-state counts:

```json
{
  "material_count": 17,
  "shader_counts": {
    "Glass": 1,
    "Illum": 15,
    "Multilayeredmaterials": 1
  },
  "string_gen_masks": {
    "": 1,
    "%NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING": 14,
    "%NORMAL_MAP%SUBSURFACE_SCATTERING": 1,
    "%SPECULAR_MAP%TINT_MAP": 1
  },
  "mtl_flags": {
    "524416": 15,
    "526464": 1,
    "526466": 1
  }
}
```

`docs/car_material_state_compare.json` is the gate for this. Its
`comparison.ok` value is `true`, and it checks per-material shader, MtlFlags,
GenMask, StringGenMask, and PublicParams values. The same report is also embedded
under `material_state_compare` in the RC smoke material report; a mismatch makes
`tools.rc_smoke_test` return failure.

The material mapping report is now also a smoke gate. If its summary marks
`action_required=true`, `tools.rc_smoke_test` returns failure. This keeps used
`<unassigned>` materials and failed CGF material-id checks from being treated as
a successful RC conversion just because RC returned `0`.

The PySide FBX/JSON export path uses `tools.rc_export_gate` for the same direct
RC import checks instead of calling `RCImportRunner` by itself. That keeps the
interactive export path aligned with the smoke flow: RC success, material mapping
summary, MTL schema gate, and texture output gate must all be clean.

The same RC smoke run also embeds the texture output gate under
`texture_output_gate` in the material report. A texture gate mismatch also makes
`tools.rc_smoke_test` return failure, so the car user flow now checks RC
conversion, material slots, material state, and texture output naming in one
coarse command.

The generated MTL is also scanned by `tools.mtl_schema_report` during the RC
smoke run. Its gate fails on unknown CryEngine texture maps, mismatched
source-backed texture suffixes, and unknown `MtlFlags` masks. The material report
embeds the MTL gate under `mtl_schema_gate`.

Material report result:

```json
{
  "rc_success": true,
  "output_exists": true,
  "slot_alignment_ok": true,
  "cgf_material_id_alignment_ok": true,
  "cgf_import_settings_alignment_ok": true,
  "fixture_material_semantic_alignment_ok": true,
  "request_material_count": 17,
  "mtl_slot_count": 17,
  "cgf_material_id_count": 16,
  "failed_material_id_check_count": 0,
  "unassigned_placeholder_count": 1,
  "unassigned_slots_ok": true,
  "action_required": false
}
```

Texture output gate result:

```json
{
  "group_count": 17,
  "output_count": 73,
  "diagnostic_count": 0,
  "ok": true
}
```

MTL schema gate result:

```json
{
  "ok": true,
  "diagnostic_count": 0,
  "error_count": 0,
  "warning_count": 0
}
```

Direct RC export gate result:

```json
{
  "rc_success": true,
  "action_required": false,
  "mtl_schema_gate_ok": true,
  "texture_output_gate_ok": true
}
```

## Batch Policy

Going forward, avoid adding one document and one RC run per tiny rule. Use this
larger batch rhythm instead:

1. mine a sample or source-backed schema into a machine-readable rule set
2. apply a batch of low-risk rules through shared data channels
3. run one focused suite for changed modules
4. run one full suite and one RC smoke flow
5. commit the whole batch with one durable doc/report pair

## Verification

```powershell
uv run python -m pytest tests/test_mtl_exporter.py tests/test_material_texture_resolver.py tests/test_mtl_override_extractor.py tests/test_rc_smoke_test.py
uv run python -m pytest tests/test_mtl_material_state_compare.py tests/test_mtl_override_extractor.py tests/test_mtl_exporter.py tests/test_rc_smoke_test.py
uv run python -m pytest tests/test_rc_smoke_test.py tests/test_texture_output_diagnostics.py
uv run python -m pytest tests/test_mtl_schema_report.py tests/test_rc_smoke_test.py
uv run python -m pytest tests/test_rc_smoke_test.py
uv run python -m pytest tests/test_rc_export_gate.py tests/test_rc_smoke_test.py tests/test_material_mapping_report.py tests/test_mtl_schema_report.py tests/test_texture_output_diagnostics.py
uv run python -m pytest
uv run python -m compileall model_processing output_formats tools tests
uv run python tools/converter_schema.py --check docs/converter_schema.json
uv lock --check
```

Result:

- `71 passed`
- `58 passed`
- `46 passed`
- `45 passed`
- `40 passed`
- `97 passed`
- `416 passed`
- `compileall` completed
- converter schema snapshot is current
- `uv lock --check` passed
