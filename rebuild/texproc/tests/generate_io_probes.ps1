param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"

$magick = Get-Command magick -ErrorAction Stop
$outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

$tiffPath = Join-Path $outputRoot "probe_gray16.tif"
$exrPath = Join-Path $outputRoot "probe_rgba16.exr"

& $magick.Source -size 2x2 "gradient:black-white" -colorspace sRGB -depth 16 $tiffPath
if ($LASTEXITCODE -ne 0) {
    throw "ImageMagick failed to generate $tiffPath"
}

& $magick.Source -size 2x2 "gradient:black-white" -colorspace sRGB -depth 16 $exrPath
if ($LASTEXITCODE -ne 0) {
    throw "ImageMagick failed to generate $exrPath"
}

& $magick.Source identify -format "%f width=%w height=%h depth=%z channels=%[channels]`n" $tiffPath $exrPath
if ($LASTEXITCODE -ne 0) {
    throw "ImageMagick failed to inspect generated probes"
}
