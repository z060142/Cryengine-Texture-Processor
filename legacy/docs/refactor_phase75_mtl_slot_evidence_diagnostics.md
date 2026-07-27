# Refactor Phase 75: MTL Slot Evidence Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 1 item: stabilize material mapping evidence reports without changing existing conversion behavior

## Goal

Material mapping evaluators must not crash when MTL slot evidence is malformed.

The normal `load_mtl_slots()` path reads slot indices from XML order and produces valid rows. But tests, probes, and future external tools can call the evaluators directly with malformed MTL slot evidence. Those evaluator entrypoints must treat MTL slots as evidence, not trusted control flow.

## New Report Evidence

Added to `fixture_material_semantic_alignment`:

```text
invalid_mtl_entries
```

Current error values:

```text
invalid_mtl_slots_collection
invalid_mtl_slot_row
invalid_mtl_slot_index
```

The top-level slot alignment report also emits failed checks with matching `type` values.

## What Changed

Updated:

```text
tools/material_mapping_report.py
```

Added report/evaluator-layer MTL slot normalization:

```text
_coerce_mtl_slot_index()
_valid_mtl_slots()
_invalid_mtl_entries()
```

The following evaluator paths now use only valid MTL slots:

```text
evaluate_material_slot_alignment()
evaluate_fixture_material_semantics()
evaluate_cgf_material_ids()
```

Accepted MTL slot index evidence:

```text
0
127
"0"
" 2 "
```

Rejected MTL slot index evidence:

```text
missing slot field
true
-1
1.5
"1.0"
"bad"
```

## Current Boundary

This phase does not change MTL XML parsing or MTL generation.

`load_mtl_slots()` still returns the same shape for valid MTL files. This phase only hardens the evaluator layer against malformed or fixture-provided MTL slot rows.

This phase also does not classify empty MTL material names as invalid MTL slot evidence. Empty or mismatched MTL names remain semantic mismatches through existing slot-name checks.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_mapping_report.py
uv run python -m pytest tests\test_material_mapping_report.py tests\test_rc_smoke_test.py tests\test_verify_controlled_fixture.py
```

Result:

```text
26 passed
59 passed
```

Full verification:

```powershell
uv run python -m pytest tests
uv lock --check
```

Result:

```text
279 passed
uv lock --check succeeded
```

New coverage proves:

```text
malformed MTL slot collections do not crash slot alignment
non-object MTL slot rows are reported
missing or boolean MTL slot indices are reported
numeric-string MTL slot indices are normalized for comparison
semantic material alignment reports invalid_mtl_entries
CGF material-id alignment ignores invalid MTL rows while preserving valid rows
```
