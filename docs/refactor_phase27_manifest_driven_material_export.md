# Refactor Phase 27: Manifest-Driven Material Export

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Use the RC-facing material manifest table when generating request JSON and `.mtl` files.

Before this phase:

```text
The UI could generate and show .fbx_material_manifest.json,
but request JSON and .mtl generation still mainly followed model loader material order.
```

That meant the app could display the correct RC material table but still export a request/MTL pair from a different source of truth.

## What Changed

`model_processing.material_manifest` now has:

```text
material_manifest_materials(source_materials, material_manifest_info)
```

It converts manifest table slots into normal material records:

```json
{
  "name": "Stone.001",
  "id": 2,
  "index": 1,
  "sub_index": 1,
  "auto_assigned": false
}
```

The helper also preserves same-name texture data from the source material records when available.

The following exporters now use the manifest table when `model_data["material_manifest"]` is present:

- `output_formats.rc_request_builder.build_import_request`
- `model_processing.material_texture_resolver.build_mtl_material_data`

The PySide Model Import flow now attaches `material_manifest` to the loaded `model_obj`, including after `Generate Material Table`.

The main FBX export flow also carries `model_info["material_manifest"]` onto the reloaded model before JSON export.

## Rule

When a material manifest exists, it is the source of truth for RC material slot order:

```text
manifest material slot -> request materials[].sub_index -> .mtl SubMaterials child order
```

This protects cases such as:

```text
DuplicateSurface      -> slot 0
DuplicateSurface.001  -> slot 1
```

even if the model loader or UI list has a different material order.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_material_manifest.py tests\test_rc_request_builder.py tests\test_material_texture_resolver.py tests\test_mtl_exporter.py tests\test_pyside_model_import_diagnostics.py
```

Manual sidecar check:

```text
manifest: DuplicateSurface -> 0, DuplicateSurface.001 -> 1
request:  DuplicateSurface -> 0, DuplicateSurface.001 -> 1
.mtl:     DuplicateSurface, DuplicateSurface.001
```

## Remaining Work

- Build on Phase 28's manifest-driven RC smoke path from the PySide UI.
- Export or surface semantic material alignment reports from the UI after RC runs.
- Decide whether missing sidecars should become warnings before model export.
