param(
    [string]$FactSheet,
    [string]$Resume,
    [string]$Research,
    [switch]$Online,
    [switch]$PublicInputConfirmed,
    [string]$ResumeL3,
    [switch]$RetryFailed
)

$ErrorActionPreference = 'Stop'
$ProjectDir = $PSScriptRoot
Set-Location -LiteralPath $ProjectDir
$Python = 'C:\src\anaconda3\envs\compute\python.exe'

# Console output must survive non-Latin domain and source names. Without
# this, Windows defaults to the ANSI code page and a single non-ASCII
# character in a printed path raises UnicodeEncodeError.
$env:PYTHONIOENCODING = 'utf-8'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Required compute interpreter not found: $Python"
}

if (($Online -or $PublicInputConfirmed) -and -not $Research) {
    throw '-Online and -PublicInputConfirmed require -Research.'
}
if ($Research -and -not $Online) {
    throw '-Research requires -Online.'
}
if ($Research -and -not $PublicInputConfirmed) {
    throw '-Research requires -PublicInputConfirmed.'
}
if ($RetryFailed -and -not $ResumeL3) {
    throw '-RetryFailed requires -ResumeL3.'
}
if (@($FactSheet, $Resume, $Research, $ResumeL3).Where({ $_ }).Count -gt 1) {
    throw 'Choose only one of -FactSheet, -Resume, -Research or -ResumeL3.'
}

if ($Research) {
    $Layer3Args = @('--research', $Research)
    if ($Online) {
        $Layer3Args += '--online'
    }
    if ($PublicInputConfirmed) {
        $Layer3Args += '--public-input-confirmed'
    }
    & $Python -m ML.deep_research.layer3 @Layer3Args
} elseif ($ResumeL3) {
    $Layer3Args = @('--resume-l3', $ResumeL3)
    if ($RetryFailed) {
        $Layer3Args += '--retry-failed'
    }
    & $Python -m ML.deep_research.layer3 @Layer3Args
} elseif ($Resume) {
    & $Python -m ML.deep_research.layer2 --resume $Resume
} else {
    if (-not $FactSheet) {
        $FactSheet = Read-Host 'Full path to fact_sheet.md'
    }
    & $Python -m ML.deep_research.layer2 $FactSheet
}

exit $LASTEXITCODE
