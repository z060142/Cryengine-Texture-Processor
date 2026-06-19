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

## Car Batch

Command:

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

## Verification

```powershell
uv run python -m pytest tests/test_texture_output_diagnostics.py tests/test_texture_output_paths.py tests/test_cryengine_mtl_schema.py
uv run python -m tools.texture_output_gate "S:\Crytek\crytek\Stripped to the bone\example\car" --output docs\car_texture_output_gate.json
```

Result:

- `35 passed`
- car texture gate: `ok: True`, `group_count: 17`, `output_count: 73`,
  `diagnostic_count: 0`
