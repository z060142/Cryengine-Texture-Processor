# Phase 1 Refactor Scope

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Purpose

Phase 1 is a bounded stabilization/refactor phase.

The goal is not to finish the full CryEngine/RC-correct converter. The goal is to preserve current behavior while removing misleading placeholder logic, consolidating duplicated rules, making fallbacks visible, and leaving enough diagnostics for Phase 2 to replace guessed behavior with real CryEngine/RC rules.

## Completion Rule

Phase 1 is complete when every item in the Phase 1 Remaining Work section is either:

```text
done with tests and a commit
or explicitly deferred to Phase 2/Phase 3 in this file
```

No new Phase 1 work may be added unless it fixes a regression introduced by Phase 1 itself.

## Already Completed In Phase 1

These are already done and must not be reopened unless a regression is found:

```text
Phase 40: shared material slot table
Phase 41: FBX texture path resolution
Phase 42: shared model export context
Phase 43: explicit .mtl texture path rules
Phase 44: material converter placeholder replacement
Phase 45: degraded model load status and texture source_mode
Phase 46: shared texture type resolver
Phase 47: processed texture evidence capture
```

## Phase 1 Remaining Work

### P1-1: Surface Texture Evidence In Diagnostics

Status: done in `refactor_phase48_diagnostics_texture_evidence.md`.

Problem:

`texture_ref_evidence`, `load_status`, and `source_mode` now exist, but material diagnostics sidecars and the PySide diagnostics view do not show enough of this evidence.

Done when:

```text
material_diagnostics.json records texture_ref_evidence when available
diagnostics preserve source_mode without adding non-RC fields to request JSON
PySide diagnostics can surface degraded/fallback texture evidence at least textually
tests cover the diagnostics payload
commit and docs are added
```

### P1-2: Make FBX Texture Fallback Visible

Problem:

`FbxExporter` still has a compatibility fallback that guesses `<material>_diff.tif` when processed texture data is missing. That fallback is acceptable in Phase 1, but it must not be silent.

Done when:

```text
the fallback path records or returns a machine-testable warning/diagnostic
tests cover fallback and normal processed-path behavior
normal exporter behavior is preserved
commit and docs are added
```

### P1-3: Bound Core Placeholder Modules

Problem:

These modules still contain placeholder-style manager code:

```text
core/texture_manager.py
core/model_manager.py
core/material_manager.py
```

Phase 1 should not fully redesign them. It only needs to prevent them from pretending to be complete.

Done when:

```text
current imports/callers are identified
unused placeholder managers are marked legacy/internal or given explicit narrow contracts
used manager behavior is covered by tests where practical
misleading "actual implementation" placeholder comments are removed or rewritten into true limitations
commit and docs are added
```

### P1-4: Model Import UI Shows Degraded State

Problem:

The UI stores `load_status` and `source_mode`, but users can still mistake fallback filesystem scans for authoritative Blender/FBX material data.

Done when:

```text
imported model rows or details show loaded/import_only/dummy state
texture summaries expose source_mode or an equivalent degraded-state label
tests cover formatting/helper behavior without requiring live Qt interaction where possible
commit and docs are added
```

### P1-5: Phase 1 Status Matrix

Problem:

README still has broad statements such as model export being under development. Phase 1 needs a fixed, readable status matrix so Phase 2 starts from known boundaries.

Done when:

```text
README or a linked doc lists what is supported, degraded, unsupported, and Phase-2-only
the matrix covers texture processing, model load, FBX export, request JSON, MTL export, diagnostics, RC smoke, and material masks
commit is added
```

## Explicitly Not Phase 1

These must not be pulled into Phase 1:

```text
real GenMask/StringGenMask/PublicParams replacement
Material Editor round-trip completion
full RC request schema rewrite
final Blender plugin design
new model conversion architecture from scratch
full removal of legacy Tk entry point
full removal of all compatibility fallbacks
making Sandbox launch probes pass on this machine
guaranteeing final CGF/material correctness for arbitrary assets
```

## Phase 1 Exit Gate

Before declaring Phase 1 complete, run:

```powershell
uv run python -m pytest tests
uv run python -m compileall core model_processing output_formats tests tools ui ui_pyside utils main.py legacy_tk_main.py
uv lock --check
git diff --check
```

Expected state:

```text
all tests pass
compileall passes
uv lock is unchanged
git diff --check has no real whitespace errors
worktree is clean after final Phase 1 commit
```

## Phase 2 Handoff

Phase 2 starts only after the exit gate passes.

Phase 2 is where guessed compatibility behavior is replaced with source-derived or RC-probed CryEngine rules. The first Phase 2 targets should be:

```text
GenMask/StringGenMask/PublicParams evidence
material slot and polygon material id behavior
request JSON schema and RC import behavior
MTL material defaults and shader params
```
