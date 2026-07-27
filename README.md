# CryEngine Texture Processor (v2)

[中文版說明](README_ZH.md)

Converts PBR texture sets and FBX models into CryEngine-ready assets. v2 is a
full Rust rewrite of the original Python tool (now frozen under [`legacy/`](legacy/)).

## Components

| Crate | What it does |
|---|---|
| `texproc` | CLI: scans/groups texture files, converts PBR (metallic/roughness) sets to CryEngine `_diff` / `_spec` / `_ddna` / `_displ` TIF outputs, drives RC.exe for DDS |
| `texproc-gui` | Workbench GUI: texture group review, batch conversion, FBX ingest, model export (`.mtl` + `.mtl.cryasset` + RC request JSON) |
| `converter` | CLI: FBX (via ufbx) → CryEngine `.mtl` + RC import-request JSON, material diagnostics |
| `ce-schema` | Shared CryEngine schema/policy tables (embedded snapshot) |

All executables are statically linked (`+crt-static`, see `.cargo/config.toml`)
and land in `target/release/`.

## Build

```powershell
cargo build --release
```

Requires stable Rust (2021 edition) on Windows (x86_64-pc-windows-msvc).

## Acceptance gates

```powershell
.\run_gates.ps1          # full run (RC smoke auto-skips if RC.exe not found)
.\run_gates.ps1 -SkipRC  # skip the optional RC.exe smoke tests
```

Run from **PowerShell only** — Git Bash (MSYS) rewrites `/`-prefixed arguments
(JSON pointers, RC flags) and breaks the gates. Requires `cargo` and `uv`; the
Python side of the gates (golden comparisons, E2E harness) lives in `legacy/`
and runs via `uv run --project legacy`.

Optional RC smoke: set `CE_RC_EXE` to your `rc.exe` path, or install CRYENGINE
5.7 LTS at the default location.

## Documentation

- `docs/rust-workspace-design.md` — architecture decisions (D-01…D-12) and defect rulings
- `docs/texture-pipeline-spec.md` — texture pipeline specification
- `docs/metal-gate-design.md` — metal conversion cutoff (Metal Gate) design
- `docs/cga-research.md`, `docs/helper-node-research.md` — research notes
- `docs/tickets/` — implementation tickets and records

## Legacy (v1)

The original Python/PySide implementation is preserved unmodified under
`legacy/` and serves as the verification baseline for the acceptance gates
(golden files, E2E tests). See [`legacy/README.md`](legacy/README.md).
