# CryEngine Texture Processor

[中文版说明](https://github.com/z060142/Cryengine-Texture-Processor/blob/main/README_ZH.md)

A powerful tool for processing and converting textures to CryEngine-compatible formats. This application automates the texture workflow for CryEngine projects, helping artists and developers save time and ensure consistent texture outputs.

## Features

- **Texture Import & Classification**: Automatically detects and classifies textures by type (diffuse, normal, specular, etc.)
- **Smart Texture Grouping**: Groups related textures that belong to the same material
- **Intermediate Format Processing**: Processes textures into standardized intermediate formats
- **CryEngine Output Generation**: Creates proper CryEngine texture formats:
  - _diff (Diffuse)
  - _spec (Specular)
  - _ddna (Normal & Gloss combined)
  - _displ (Displacement)
  - _emissive (Emissive)
  - _sss (Subsurface Scattering)
- **Advanced Processing Options**:
  - Convert Metallic/Roughness PBR textures to CryEngine spec/gloss workflow
  - Automatically generate missing textures
  - Control output resolution and format
- **Model Import**: Extract textures from 3D models (FBX, OBJ, DAE, 3DS, BLEND)
- **RC Import Request Export**: Generate `request`-root JSON files for CryEngine Resource Compiler FBX conversion
- **Batch Processing**: Process multiple texture groups at once
- **DDS Generation**: Generate DDS files using RC.exe
- **Multilingual Interface**: Support for English and Traditional Chinese

> **Note:** The model export functionality is still under development and not fully implemented in the current version.

## Installation

### Prerequisites

- Python 3.10 or newer
- uv
- Pillow (PIL) library
- NumPy (version 1.x recommended for compatibility with Blender Python API)
- PySide6
- ImageMagick (for advanced image processing)
- Blender Python API (bpy), optional for model loading/export support

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/cryengine-texture-processor.git
   cd cryengine-texture-processor
   ```

2. Sync the environment with uv:
   ```bash
   uv sync
   ```

   If you need Blender Python API support and your Python version has a compatible `bpy` wheel:
   ```bash
   uv sync --extra model
   ```

3. Start the PySide application:
   ```bash
   uv run python main.py
   ```

The old Tkinter entry point is preserved as `legacy_tk_main.py` during the migration.

## Usage

### Importing Textures

1. Click the "Import Textures" button
2. Select texture files (JPG, PNG, TGA, TIF, etc.)
3. The application will automatically classify textures and group related ones

### Processing Textures

1. Review the detected texture groups
2. Configure export settings:
   - Output directory
   - Diffuse format (albedo or diffuse_ao)
   - Toggle normal map green channel flip
   - Enable/disable specular generation
   - Select output format and resolution
3. Click "Export Textures" or "Batch Process" to process all texture groups

### Working with 3D Models

1. Switch to the "Model Import" tab
2. Import a 3D model (FBX, OBJ, etc.)
3. Extract textures from the model
4. Add extracted textures to the processing queue

### RC FBX Smoke Test

The repository includes a repeatable smoke harness for CryEngine Resource Compiler FBX conversion:

```bash
uv run python -m tools.rc_smoke_test --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_default" --asset-name "CubeA_default_smoke" --materials "Default"
```

When local CryEngine 5.7.1 and GameSDK sample folders are present, the harness discovers `rc.exe` and `objects\cubao\CubeA.fbx` automatically. The verified run writes a `.fbx`, `.mtl`, `.json`, `.cgf`, and `.cryasset` bundle under the selected work directory.

The harness also writes `<asset>.material_report.json`, which compares RC request material `sub_index` values with generated `.mtl` sub-material slots and records preflight material-slot diagnostics.

Existing `.cgf` files can be inspected with:

```bash
uv run python -m tools.cgf_material_probe path/to/asset.cgf
```

FBX material table evidence can be inspected with Blender and written as a sidecar consumed by smoke material reports:

```bash
uv run python -m tools.blender_material_inspector --fbx path/to/asset.fbx
```

When a material manifest sidecar exists, RC smoke tests can build request/MTL materials from it:

```bash
uv run python -m tools.rc_smoke_test --fbx path/to/asset.fbx --work-dir path/to/work --materials-from-manifest
```

The same manifest-driven RC smoke path is available in the PySide Model Import tab:

```text
Import FBX -> Generate Material Table -> Run RC Material Smoke
```

The UI reads `rc_exe_path` from preferences, writes the smoke bundle under `<fbx stem>_rc_smoke_work`, and shows semantic/CGF material-id alignment when the generated material report contains those checks.

Controlled Blender fixtures can be generated and verified with:

```bash
uv run python -m tools.blender_material_fixture --output-dir path/to/fixture
uv run python -m tools.verify_controlled_fixture --manifest path/to/fixture/CE_MaterialSlotProbe.fixture_manifest.json --report path/to/work/CE_MaterialSlotProbe.material_report.json
uv run python -m tools.verify_controlled_fixture --manifest path/to/fixture/CE_MaterialSlotProbe.fixture_manifest.json --report path/to/work/CE_MaterialSlotProbe.material_report.json --check-polygons
```

Material Editor save behavior for `.mtl` mask fields is being probed with:

```bash
uv run python -m tools.material_editor_roundtrip prepare --work-dir "S:\Crytek\crytek\Stripped to the bone\material_editor_roundtrip_phase37" --output docs\phase37_material_editor_roundtrip_manifest.json
uv run python -m tools.material_editor_roundtrip run --manifest docs\phase37_material_editor_roundtrip_manifest.json --timeout 180 --output docs\phase38_material_editor_roundtrip_sandbox_run_argv0.json
uv run python -m tools.material_editor_roundtrip compare --manifest docs\phase37_material_editor_roundtrip_manifest.json --output docs\phase38_material_editor_roundtrip_compare_after_argv0.json
```

Automated Sandbox `/runpython` launches must use the manifest `sandbox_popen` strategy so CryEdit's parser sees the script path as the first non-flag argument.
The harness also records `sandbox_edcommand`, a normal Editor launch strategy using `-edCommand "general.run_file '<script>'"` for environments where `/BatchMode` stalls.

## Technologies

- **Python**: Main programming language
- **Pillow (PIL)**: Image processing
- **NumPy**: Numerical operations for image processing
- **PySide6**: GUI framework
- **ImageMagick**: Advanced image processing operations
- **Blender Python API (bpy)**: Optional model loading support

## Known Limitations

- Model export functionality is still under development
- Certain advanced PBR workflow conversions may require manual tweaking
- For proper DDS generation, RC.exe path must be configured in preferences
- For model loading functionality, Blender Python API (bpy) is required or must be provided through a later Blender subprocess integration
- RC request and `.mtl` generation now preserve known FBX material slots first; existing `.mtl` name matches are only a fallback when the FBX slot is unavailable
- RC execution now uses a structured runner; a real `rc.exe` smoke test has passed with the local GameSDK `CubeA.fbx` sample
- A repeatable RC smoke harness is available via `uv run python -m tools.rc_smoke_test`
- Smoke runs now emit a material mapping report with CGF `MeshSubsets.nMatID` inspection; controlled multi-material FBX fixtures are still needed to prove polygon assignment behavior end to end
- A controlled Blender FBX fixture has verified that used material slots `0` and `1` survive RC conversion into CGF `MeshSubsets.nMatID`
- Controlled fixtures have verified that RC preserves sparse used material ids such as `0` and `2`; it does not compress them to contiguous ids
- The Material Editor round-trip harness now works around Sandbox `/runpython` argv0 parsing, but the local Sandbox still times out before producing `sandbox_roundtrip_result.json`; this is not yet evidence for Material Editor `GenMask`/`StringGenMask` preservation
- Local Sandbox probes show `/BatchMode` stalls during early system config; normal Editor `-edCommand` starts deeper but the GameSDK sample blocks at `WaitForAllowSendClientConnect` before the round-trip script runs
- A controlled request-name remap probe shows that RC keeps CGF polygon material ids aligned to raw FBX material slots; request/MTL material names do not rewrite polygon material ids when slot order differs
- A controlled deleted-material probe shows that request `sub_index = -1` does not remove geometry material ids still used by the FBX; preserve placeholder slots unless polygon usage proves the slot is unused
- Material assignment now emits diagnostics for hazardous deleted or remapped known FBX slots; smoke reports expose them as `preflight_material_diagnostics`
- The PySide model import tab surfaces material-slot diagnostics for selected models and marks imported models with `[hazard]` when needed
- Normal model export now writes `<model>.material_diagnostics.json` sidecars without adding non-RC fields to the RC request JSON
- Blender-loaded models now preserve mesh material slot order and polygon usage counts, avoiding `bpy.data.materials` placeholder slot drift
- Material diagnostics sidecars and the PySide diagnostics table now show polygon usage counts when known
- Material diagnostics now warn when multiple meshes use the same FBX slot with different material names
- RC request, `.mtl`, diagnostics, and smoke preflight now share `model_processing.material_slot_table` as the single material slot assignment entry point
- FBX material export now uses the resolver-produced processed `diff` texture path when available and resolves relative texture directories next to the exported FBX
- The PySide model export flow now prepares MTL, FBX, JSON, and diagnostics paths through `model_processing.model_export_context`
- `.mtl` texture path emission now preserves CryEngine `%...%` aliases and uses explicit tested relative/absolute fallback rules
- Controlled multi-mesh probes show that raw per-object local FBX slot ids are not enough: two meshes can both use local slot `0`, while RC writes CGF material ids `0` and `1`; a swapped request/MTL probe shows RC does not remap those ids by material name, so request/MTL slot order must mirror the exported FBX material table
- Shared-material and duplicate-name probes show that Blender suffixes such as `.001` are RC-visible material identities, not cosmetic noise; request JSON and `.mtl` generation must preserve them unless the exporter deliberately creates another stable unique name
- RC smoke material reports now read controlled fixture manifests when available and emit `fixture_material_semantic_alignment`, which distinguishes "CGF id exists" from "that id points to the expected material name"
- A Blender FBX material inspector can now emit `.fbx_material_manifest.json` sidecars so non-fixture FBX files can use the same semantic material report path
- The PySide Model Import tab now reads `.fixture_manifest.json` / `.fbx_material_manifest.json` sidecars and displays the RC material table slots when available
- The PySide Model Import tab can generate `.fbx_material_manifest.json` sidecars for selected FBX models through Blender and refresh the RC material table view
- Request JSON and `.mtl` generation now use `model_data["material_manifest"]` as the RC material slot source of truth when present
- RC smoke tests can now use `--materials-from-manifest` to build request JSON and `.mtl` directly from a fixture or Blender FBX material manifest sidecar
- The PySide Model Import tab can run manifest-driven RC material smoke for a selected FBX and summarize semantic / CGF material-id alignment from the generated material report
- `.mtl` XML generation now uses named document-builder helpers, but current shader/GenMask/PublicParams values are still guessed and need replacement with real CryEngine evidence
- CryEngine `.mtl` texture map names and Illum shader token masks are now captured in `output_formats/cryengine_mtl_schema.py`; exporter GenMask numeric values remain compatibility-preserved until real RC/Material Editor comparison is complete
- `tools.mtl_mask_report` can compare real `.mtl` samples against Illum.ext, ShaderCore common legacy-fix, and exporter compatibility mask tables; current samples show persisted `GenMask` needs the full renderer remap path
- `tools.cryengine_shader_flags` can rebuild the current source-derived common global flag table from `Engine/Shaders/*.ext`, but that table still does not match persisted engine `.mtl` samples, so exporter `GenMask` remains compatibility-preserved
- `tools.cryengine_shader_flags` can also parse CryEngine generated `Shaders/Cache/globals.txt`, and `tools.mtl_mask_report` accepts `--globals-file` as the preferred runtime common-global mask source
- Local CryEngine 5.7.1 `globals.txt` caches still do not match inspected persisted EngineAssets `.mtl` `GenMask` values, so the next material phase must probe RC / Material Editor round-trip behavior before changing exporter mask generation
- `tools.mtl_genmask_probe` shows RC 5.7.1 accepts FBX imports with missing or contradictory `.mtl` `GenMask` / `StringGenMask`, so RC success only proves conversion acceptance, not material shader-mask correctness
- `tools.mtl_schema_report` summarizes real `.mtl` XML usage; source tracing shows runtime/editor load reads `GenMask` first but lets `StringGenMask` remap it, while Editor save writes both fields and shader-dependent `PublicParams`
- `tools.material_editor_roundtrip` prepares Material Editor load/save fixtures and compares before/after `.mtl` XML; the current Sandbox `/runpython` attempt timed out before producing round-trip evidence

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- CryEngine for their texture format specifications
- The Pillow and NumPy communities for their excellent image processing libraries
- Contributors and testers who have helped improve the application
