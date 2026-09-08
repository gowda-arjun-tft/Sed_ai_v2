param(
    [string]$FactSheet,
    [string]$DomainPlugin,
    [string]$Requirements,
    [string]$Resume,
    [string]$Research,
    [string]$ExternalResearch,
    [switch]$Online,
    [switch]$PublicInputConfirmed,
    [string]$ResumeL3,
    [string]$ResumeL4,
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

if (($Online -or $PublicInputConfirmed) -and -not ($Research -or $ExternalResearch)) {
    throw '-Online and -PublicInputConfirmed require -Research or -ExternalResearch.'
}
if ($Research -and -not $Online) {
    throw '-Research requires -Online.'
}
if ($Research -and -not $PublicInputConfirmed) {
    throw '-Research requires -PublicInputConfirmed.'
}
if ($ExternalResearch -and -not $Online) {
    throw '-ExternalResearch requires -Online.'
}
if ($ExternalResearch -and -not $PublicInputConfirmed) {
    throw '-ExternalResearch requires -PublicInputConfirmed.'
}
if ($RetryFailed -and -not ($ResumeL3 -or $ResumeL4)) {
    throw '-RetryFailed requires -ResumeL3 or -ResumeL4.'
}
if (@($FactSheet, $Resume, $Research, $ResumeL3, $ExternalResearch, $ResumeL4).Where({ $_ }).Count -gt 1) {
    throw 'Choose only one run action.'
}
if (($DomainPlugin -or $Requirements) -and ($Resume -or $Research -or $ResumeL3 -or $ExternalResearch -or $ResumeL4)) {
    throw '-DomainPlugin and -Requirements apply only to new Layer 2 runs.'
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
} elseif ($ExternalResearch) {
    $Layer4Args = @('--external-research', $ExternalResearch, '--online', '--public-input-confirmed')
    & $Python -m ML.deep_research.layer4 @Layer4Args
} elseif ($ResumeL3) {
    $Layer3Args = @('--resume-l3', $ResumeL3)
    if ($RetryFailed) {
        $Layer3Args += '--retry-failed'
    }
    & $Python -m ML.deep_research.layer3 @Layer3Args
} elseif ($ResumeL4) {
    $Layer4Args = @('--resume-l4', $ResumeL4)
    if ($RetryFailed) {
        $Layer4Args += '--retry-failed'
    }
    & $Python -m ML.deep_research.layer4 @Layer4Args
} elseif ($Resume) {
    & $Python -m ML.deep_research.layer2 --resume $Resume
} else {
    if (-not $FactSheet) {
        $FactSheet = Read-Host 'Full path to fact_sheet.md'
    }
    if (-not $DomainPlugin -or -not $Requirements) {
        throw 'A new Layer 2 run requires -DomainPlugin and -Requirements.'
    }
    & $Python -m ML.deep_research.layer2 $FactSheet --domain-plugin $DomainPlugin --requirements $Requirements
}

exit $LASTEXITCODE
