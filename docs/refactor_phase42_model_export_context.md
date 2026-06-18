# Refactor Phase 42: Shared Model Export Context

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Preserve current model export behavior while reducing duplicated material and texture preparation in the PySide export flow.

Before this phase, `main.py` prepared model export data independently for:

```text
MTL export
FBX export
JSON export
material diagnostics
thumbnail / RC runner paths
```

The duplicated setup made later CryEngine/RC rule replacement risky because each artifact could accidentally see a different material list, manifest state, texture reference set, or output basename.

## What Changed

Added:

```text
model_processing/model_export_context.py
```

Main helpers:

```text
attach_material_manifest()
build_model_export_context()
ModelExportContext
```

The shared context now prepares:

```text
base filename
MTL filename
FBX filename
FBX output path
model-local texture directory
existing .mtl sub-material names
texture refs
MTL material data
FBX texture data
```

`main.py` still owns UI progress, Blender reload behavior, export calls, RC execution, and error handling. The new context only centralizes the data preparation used by those calls.

## Preserved Behavior

The refactor preserves these existing decisions:

```text
MTL export uses the already imported model object from the UI
FBX export reloads the source model through Blender before export
non-exportable dummy/import-only models are skipped
FBX export still requires processed diffuse texture data
JSON export still references the exported FBX filename
material diagnostics still compare against any existing .mtl sub-material list
thumbnails are still generated from the exported FBX path after successful FBX export
```

## Why This Matters

The next material phase needs request JSON, `.mtl`, FBX texture links, and diagnostics to agree on one prepared model view.

This phase moves toward that end state without claiming new CryEngine behavior:

```text
model data + material manifest + texture refs
  -> shared export context
  -> MTL / FBX / JSON / diagnostics consumers
```

Once the real RC material and shader rules are proven, they can be inserted into the context or its lower-level resolvers instead of patched independently into each UI export branch.

## Verification

Passed targeted verification:

```powershell
uv run python -m pytest tests\test_model_export_context.py tests\test_material_texture_resolver.py tests\test_fbx_exporter.py
uv run python -m compileall main.py model_processing tests
```

New tests cover:

```text
sidecar material manifest attachment
shared output filename/path derivation
shared MTL and FBX processed texture data generation
manifest-driven MTL material ordering through the context
```
