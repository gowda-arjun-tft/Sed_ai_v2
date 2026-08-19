param(
    [Alias('FactSheet')]
    [string]$InputJson,
    [string]$Resume
)

$ErrorActionPreference = 'Stop'
$ProjectDir = $PSScriptRoot
Set-Location -LiteralPath $ProjectDir
$Python = 'C:\src\anaconda3\envs\compute\python.exe'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Required compute interpreter not found: $Python"
}

if ($Resume) {
    & $Python -m ML.deep_research.layer2 --resume $Resume
} else {
    if (-not $InputJson) {
        $InputJson = Read-Host 'Full path to claims.json'
    }
    & $Python -m ML.deep_research.layer2 $InputJson
}

exit $LASTEXITCODE
