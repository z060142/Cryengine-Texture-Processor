# Texture Output Gate Batch

## Why

The texture converter needs a coarse gate that answers one practical question:
can the files in an output folder be handed to CryEngine RC as material textures?

This batch keeps the rule at folder level instead of splitting every texture
case into a separate phase. The gate scans an output directory, groups files by
CryEngine suffix, applies the shared `.mtl` texture map policy, and writes one
JSON report.

## Files

- `tools/texture_output_gate.py`
- `output_formats/texture_output_diagnostics.py`
- `output_formats/texture_output_paths.py`
- `output_formats/cryengine_mtl_schema.py`
- `docs/car_texture_output_gate.json`

## Gate Rules

Accepted RC source extensions are still source-backed by
`TextureCompiler::IsImageFormatSupported`:

```text
dds, hdr, tif
```

The folder scanner recognizes these processed texture suffixes:

```text
diff      -> _diff
spec      -> _spec
ddna      -> _ddn, _ddna
displ     -> _displ
emissive  -> _em, _emissive
sss       -> _sss
opacity   -> _opacity
roughness -> _roughness
```

Important behavior:

- unknown image suffixes are reported as `unknown_texture_output_key`
- unsupported RC source extensions are reported as
  `unsupported_rc_texture_output_extension`
- missing files can be checked with the shared policy path
- CryEngine thumbnail sidecars such as `*.dds.thmb.png` are ignored
- `_emissive` is accepted as an Emittance alias because the car sample uses it
- `_roughness` remains an observed compatibility alias mapped to the CE Opacity
  texture map

## Batch Enforcement

`BatchProcessor` now runs the same policy in strict mode for generated outputs.
Strict mode checks that each exporter-returned path exists on disk, in addition
to checking suffix and RC-supported source extension.

The processor records:

```text
texture_output_report_path
texture_output_report
texture_output_gate_ok
```

The PySide entry point treats `texture_output_gate_ok = false` as a failed
texture batch instead of showing a successful export with hidden diagnostics.

Tiny raw texture batch result:

```json
{
  "group_count": 1,
  "output_count": 1,
  "diagnostic_count": 0,
  "ok": true
}
```

Evidence report:

```text
docs/raw_texture_output_gate_report.json
```

## Car Batch

Standalone command:

```powershell
uv run python -m tools.texture_output_gate "S:\Crytek\crytek\Stripped to the bone\example\car" --output docs\car_texture_output_gate.json
```

Result:

```json
{
  "group_count": 17,
  "output_count": 73,
  "diagnostic_count": 0,
  "ok": true
}
```

The first raw run produced 79 diagnostics. Those collapsed to zero after the
scanner ignored `.thmb` sidecars and the shared schema accepted `_emissive` as an
Emittance alias. No ad hoc cleanup was required in the sample folder.

## RC Smoke Integration

`tools.rc_smoke_test` now runs this same gate automatically when
`--texture-output-dir` is supplied. The report is written to
`--texture-output-gate-output` when provided, otherwise beside the generated RC
request in the work directory.

The material report embeds the gate under `texture_output_gate` and records
`texture_output_gate_path`. If the gate summary is not ok, the whole RC smoke run
returns failure. This keeps the user flow coarse:

```text
FBX + manifest + material overrides + texture folder
-> generated JSON/MTL
-> RC.exe CGF
-> material slot report
-> material state compare
-> texture output gate
```

Car RC smoke texture gate result:

```json
{
  "group_count": 17,
  "output_count": 73,
  "diagnostic_count": 0,
  "ok": true
}
```

## Verification

```powershell
uv run python -m pytest tests/test_texture_output_diagnostics.py tests/test_texture_output_paths.py tests/test_cryengine_mtl_schema.py
uv run python -m pytest tests/test_rc_smoke_test.py tests/test_texture_output_diagnostics.py
uv run python -m tools.texture_output_gate "S:\Crytek\crytek\Stripped to the bone\example\car" --output docs\car_texture_output_gate.json
uv run python -m tools.rc_smoke_test --rc "S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe" --fbx "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase127_material_overrides\kb3d_citycarsessentialssedan-native.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase127_material_overrides\rc_work" --asset-name kb3d_citycarsessentialssedan-native --materials-from-manifest --material-overrides docs\car_native_material_overrides.json --reference-mtl "S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.mtl" --material-state-compare-output docs\car_material_state_compare.json --texture-output-dir "S:\Crytek\crytek\Stripped to the bone\example\car" --texture-output-format "dds,tif" --texture-output-gate-output docs\car_rc_smoke_texture_output_gate.json
```

Result:

- `35 passed`
- `46 passed`
- car texture gate: `ok: True`, `group_count: 17`, `output_count: 73`,
  `diagnostic_count: 0`
- RC smoke: `success: True`; embedded texture gate summary is also ok
- raw texture batch: `ok: True`, `group_count: 1`, `output_count: 1`,
  `diagnostic_count: 0`
