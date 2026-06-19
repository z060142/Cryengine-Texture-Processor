# Refactor Phase 47: Processed Texture Evidence

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Keep the current processed texture lookup behavior while tying it to the shared texture type resolver and recording the evidence used for each material.

Before this phase, `material_texture_resolver.py` had its own hard-coded list of suffixes to strip from texture filenames. Phase 46 introduced `texture_type_resolver.py`, so the base-name stripping rules had become duplicated again.

## What Changed

Updated:

```text
model_processing/material_texture_resolver.py
```

The material texture resolver now imports:

```text
FILENAME_SUFFIX_TYPES
infer_texture_type_from_path()
```

from:

```text
model_processing/texture_type_resolver.py
```

`COMMON_TEXTURE_BASE_SUFFIXES` is now derived from the shared suffix table instead of maintaining a separate list.

Material texture records now include:

```text
texture_ref_evidence
```

Each evidence item records:

```text
path
filename
texture_type
source_mode
```

`build_mtl_material_data()` carries this evidence through to the material dictionaries it returns. Existing MTL/FBX exporters ignore the extra field, preserving output behavior.

## Preserved Behavior

Processed texture lookup still uses:

```text
TextureManager.classify_texture() when available and the source file exists
filename suffix stripping as fallback
existing processed output files only
```

FBX output still uses:

```text
diff -> _diff
ddna -> _ddna
```

MTL output still uses:

```text
diffuse -> _diff
normal -> _ddna
specular -> _spec
displacement -> _displ
emissive -> _emissive
opacity -> _opacity
sss -> _sss
```

## Why This Matters

The converter now distinguishes Blender material evidence from degraded filesystem-scan evidence. Processed texture resolution needs to preserve that distinction instead of collapsing it into only final texture paths.

This phase makes later diagnostics possible:

```text
material slot
  -> source texture refs and source_mode
  -> resolved base name
  -> processed CE texture outputs
```

That chain is needed before replacing guessed material behavior with stricter CryEngine/RC rules.

## Verification

Passed targeted verification:

```powershell
uv run python -m pytest tests\test_material_texture_resolver.py tests\test_texture_type_resolver.py tests\test_model_export_context.py tests\test_mtl_exporter.py
uv run python -m compileall model_processing\material_texture_resolver.py tests\test_material_texture_resolver.py
```

New tests cover:

```text
base-name stripping through shared suffix coverage
opacity suffix handling
texture_ref_evidence capture
MTL material data carrying empty evidence for materials with no source refs
```
