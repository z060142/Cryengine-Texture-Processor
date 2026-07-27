# Refactor Phase 43: MTL Texture Path Rules

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Make `.mtl` texture path emission explicit and test-covered while preserving the existing CryEngine material XML shape.

Before this phase, `_calculate_relative_path()` worked for simple same-folder texture paths, but it had three weak spots:

```text
CryEngine aliases such as %ENGINE% were treated like filesystem paths
absolute paths were not normalized before relative-path calculation
cross-drive fallback returned only the filename, which could silently point to the wrong texture
```

## What Changed

Updated:

```text
output_formats/mtl_exporter.py
```

The `.mtl` texture path helper now follows these rules:

```text
empty target/start path -> empty string
%ENGINE% or other %...% CryEngine alias -> preserve alias and normalize slashes
relative texture path -> normalize slashes and add ./ when needed
absolute texture path on same drive -> path relative to the .mtl output directory
absolute texture path on another drive -> normalized absolute path fallback
```

The last fallback is intentionally honest. A basename-only fallback can look valid while referring to a texture that is not actually next to the `.mtl`.

## Preserved Behavior

The exporter still:

```text
emits Texture nodes with CryEngine map names from CE_TEXTURE_MAP_TYPES
uses ./ for local relative texture files
uses ../ when textures are outside the model output folder
keeps the existing shader-mask and PublicParams generation behavior
keeps the existing .mtl.cryasset dependency generation path calculation
```

This phase does not change shader masks, `GenMask`, `StringGenMask`, or material slot assignment.

## Why This Matters

FBX export now points at resolver-produced processed texture files. The `.mtl` must represent those same processed files without silently changing the path when outputs are split across model and texture directories.

This phase turns the current path rules into a small tested contract before the next CryEngine/RC-specific material logic is replaced.

## Verification

Passed targeted verification:

```powershell
uv run python -m pytest tests\test_mtl_exporter.py tests\test_model_export_context.py
uv run python -m compileall output_formats tests
```

New tests cover:

```text
CryEngine %ENGINE% alias preservation
absolute texture path normalization to ./ relative paths
parent-directory relative paths
cross-drive absolute fallback
```
