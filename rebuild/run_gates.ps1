[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$rebuildRoot = $PSScriptRoot
$repoRoot = Split-Path -Parent $rebuildRoot
$previousLocation = Get-Location
$previousConverterExe = $env:CE_CONVERTER_EXE
$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$tempRoot = Join-Path $tempBase ("cryengine-texture-processor-gates-" + [guid]::NewGuid().ToString("N"))

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory)]
        [string]$Name,
        [Parameter(Mandatory)]
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Name"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

try {
    if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
        throw "cargo is required"
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv is required for the Python asset_flow gate"
    }

    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    Set-Location $rebuildRoot

    Invoke-NativeStep "Build release workspace" {
        & cargo build --workspace --release --locked
    }
    Invoke-NativeStep "Run Rust workspace tests" {
        & cargo test --workspace --release --locked
    }

    $converterExe = Join-Path $rebuildRoot "target\release\converter.exe"
    if (-not (Test-Path -LiteralPath $converterExe -PathType Leaf)) {
        throw "release converter was not produced at $converterExe"
    }
    $env:CE_CONVERTER_EXE = $converterExe

    $dumpPath = Join-Path $tempRoot "car-dump.json"
    $reportPath = Join-Path $tempRoot "car-report.json"
    Invoke-NativeStep "T-003 dump evidence" {
        & $converterExe dump "fixtures\car\car.fbx" --out $dumpPath
    }
    $actualDumpHash = (Get-FileHash -LiteralPath $dumpPath -Algorithm SHA256).Hash
    $expectedDumpHash = "332F2A2ADB5DB0210797321C6F8F7ADB92AD9E94E1BC8C8543CD717049BB8FC0"
    if ($actualDumpHash -ne $expectedDumpHash) {
        throw "T-003 dump hash mismatch: expected $expectedDumpHash, actual $actualDumpHash"
    }
    Write-Host "dump SHA-256: $actualDumpHash"

    Invoke-NativeStep "T-004 report evidence" {
        & $converterExe report "fixtures\car\car.fbx" `
            --manifest "fixtures\car\car.fbx_material_manifest.json" `
            --out $reportPath
    }
    Invoke-NativeStep "T-004 direct RC request-material golden" {
        & uv run python "..\tools\compare_json_golden.py" `
            "..\docs\car_direct_rc_export_material_report.json" $reportPath `
            --expected-pointer "/request_materials" `
            --actual-pointer "/golden_policy_projection/request_materials"
    }
    Invoke-NativeStep "T-004 trailing-unassigned request-material golden" {
        & uv run python "..\tools\compare_json_golden.py" `
            "..\docs\phase104_car_trailing_unassigned_material_report.json" $reportPath `
            --expected-pointer "/request_materials" `
            --actual-pointer "/golden_policy_projection/request_materials"
    }
    Invoke-NativeStep "T-004 material-slot evidence golden" {
        & uv run python "..\tools\compare_json_golden.py" `
            "..\docs\current_car_user_flow_material_slot_evidence.json" $reportPath `
            --expected-pointer "/material_slot_evidence/rows" `
            --actual-pointer "/material_slot_evidence/rows" `
            --expected-field "slot=/slot" `
            --expected-field "name=/request_names/0" `
            --expected-field "used=/used_by_cgf" `
            --expected-field "placeholder=/is_unassigned_placeholder" `
            --actual-field "slot=/slot" `
            --actual-field "name=/name" `
            --actual-field "used=/used_by_source" `
            --actual-field "placeholder=/is_unassigned_placeholder"
    }

    $textureDir = Join-Path $tempRoot "example\car"
    $outDir = Join-Path $tempRoot "phase\rc_work"
    New-Item -ItemType Directory -Force -Path $textureDir, $outDir | Out-Null
    $generatedMtlReference = Join-Path $rebuildRoot "fixtures\car\car-generated-reference.mtl"
    [xml]$generatedMtl = Get-Content -LiteralPath $generatedMtlReference -Raw
    foreach ($texture in $generatedMtl.SelectNodes("//Texture[@File]")) {
        $filename = Split-Path -Leaf ($texture.File -replace "/", "\")
        $texturePath = Join-Path $textureDir $filename
        if (-not (Test-Path -LiteralPath $texturePath)) {
            New-Item -ItemType File -Path $texturePath | Out-Null
        }
    }

    Invoke-NativeStep "T-005 convert" {
        & $converterExe convert "fixtures\car\car.fbx" `
            --manifest "fixtures\car\car.fbx_material_manifest.json" `
            --overrides "..\docs\car_native_material_overrides.json" `
            --texture-dir $textureDir `
            --out-dir $outDir
    }
    $requestPath = Join-Path $outDir "kb3d_citycarsessentialssedan-native.json"
    $mtlPath = Join-Path $outDir "kb3d_citycarsessentialssedan-native.mtl"
    Invoke-NativeStep "T-005 request golden" {
        & uv run python "..\tools\compare_json_golden.py" `
            "fixtures\car\car-reference.request.json" $requestPath `
            --allow-path-separators
    }
    Invoke-NativeStep "T-005 generated MTL golden" {
        & uv run python "..\tools\compare_xml_golden.py" `
            "fixtures\car\car-generated-reference.mtl" $mtlPath
    }

    Invoke-NativeStep "T-005 request schema gate" {
        & $converterExe validate $requestPath
    }
    $gatePath = [IO.Path]::ChangeExtension($requestPath, "schema_gate.json")
    Invoke-NativeStep "T-005 schema-gate golden" {
        & uv run python "..\tools\compare_json_golden.py" `
            "..\docs\car_direct_rc_export_mtl_schema_gate.json" $gatePath `
            --expected-pointer "/gate/summary" `
            --actual-pointer "/gate/summary"
    }

    $assetFlowTests = Get-ChildItem -LiteralPath (Join-Path $repoRoot "tests") `
        -Filter "test_asset_flow_*.py" |
        Sort-Object Name |
        ForEach-Object FullName
    Invoke-NativeStep "Python asset_flow E2E" {
        & uv run pytest @assetFlowTests -q
    }

    Write-Host ""
    Write-Host "ALL GATES PASSED"
}
finally {
    Set-Location $previousLocation
    $env:CE_CONVERTER_EXE = $previousConverterExe
    $resolvedTempRoot = [IO.Path]::GetFullPath($tempRoot)
    if (
        (Test-Path -LiteralPath $resolvedTempRoot) -and
        $resolvedTempRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)
    ) {
        Remove-Item -LiteralPath $resolvedTempRoot -Recurse -Force
    }
}
