param(
    [Parameter(Mandatory=$true)]
    [string]$Mt5DataDirectory
)

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/helpertz51/ICT_Library_MQ5.git"
$WorkDir = Join-Path $env:TEMP "ICT_Library_MQ5"

if (-not (Test-Path -LiteralPath $Mt5DataDirectory -PathType Container)) {
    throw "MT5 data directory does not exist: $Mt5DataDirectory"
}

if (Test-Path (Join-Path $WorkDir ".git")) {
    git -C $WorkDir pull --ff-only
} else {
    git clone $RepoUrl $WorkDir
    if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
}

$IncludeTarget = Join-Path $Mt5DataDirectory "MQL5\Include\SMC"
$ExpertsTarget = Join-Path $Mt5DataDirectory "MQL5\Experts"
New-Item -ItemType Directory -Force -Path $IncludeTarget, $ExpertsTarget | Out-Null
Copy-Item -Path (Join-Path $WorkDir "Include\SMC\*") -Destination $IncludeTarget -Recurse -Force
Copy-Item -LiteralPath (Join-Path $WorkDir "Experts\SMC_Snapshot_Export.mq5") -Destination $ExpertsTarget -Force

Write-Host "ICT SMC files copied. Open MetaEditor and compile SMC_Snapshot_Export.mq5."
Write-Host "This exporter is data-only; it does not send trade orders."
