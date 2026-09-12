param(
    [string]$FactSheet,
    [string]$DomainPlugin,
    [string]$Requirements,
    [ValidateSet('low', 'medium', 'high')]
    [string]$Layer2WebSearchDepth = 'medium',
    [ValidateSet('low', 'medium', 'high')]
    [string]$Layer2WebSearchVerbosity = 'medium',
    [string]$Resume,
    [string]$Research,
    [string]$ResearchFromL3,
    [ValidateSet('low', 'medium', 'high', 'max')]
    [string]$ResearchReasoningEffort = 'max',
    [string]$SourceSuggestion,
    [string]$ResearchInstruction,
    [string]$ExternalResearch,
    [switch]$Online,
    [switch]$PublicInputConfirmed,
    [string]$ResumeL3,
    [string]$UploadDocumentsL3,
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

if (-not ($Research -or $ResearchFromL3 -or $ResumeL3 -or $UploadDocumentsL3) -and -not (Test-Path -LiteralPath $Python)) {
    throw "Required compute interpreter not found: $Python"
}

if ($Online -and -not ($Research -or $ResearchFromL3 -or $ExternalResearch)) {
    throw '-Online requires -Research or -ExternalResearch.'
}
if ($PublicInputConfirmed -and ($Resume -or $ResumeL3 -or $ResumeL4 -or $UploadDocumentsL3)) {
    throw 'Resume uses the frozen public-input confirmation.'
}
if (($Research -or $ResearchFromL3) -and -not $Online) {
    throw '-Research requires -Online.'
}
if (($Research -or $ResearchFromL3) -and -not $PublicInputConfirmed) {
    throw '-Research requires -PublicInputConfirmed.'
}
if ($ExternalResearch -and -not $Online) {
    throw '-ExternalResearch requires -Online.'
}
if ($ExternalResearch -and -not $PublicInputConfirmed) {
    throw '-ExternalResearch requires -PublicInputConfirmed.'
}
if ($RetryFailed -and -not ($ResumeL3 -or $ResumeL4 -or $UploadDocumentsL3)) {
    throw '-RetryFailed requires -ResumeL3, -ResumeL4 or -UploadDocumentsL3.'
}
if ($SourceSuggestion -and -not $Research) {
    throw '-SourceSuggestion applies only to a new Layer 3 source-discovery run.'
}
if ($ResearchInstruction -and -not ($Research -or $ResearchFromL3)) {
    throw '-ResearchInstruction applies only to a new Layer 3 research run.'
}
if ($PSBoundParameters.ContainsKey('ResearchReasoningEffort') -and -not ($Research -or $ResearchFromL3)) {
    throw '-ResearchReasoningEffort applies only to a new Layer 3 research run.'
}
if (@($FactSheet, $Resume, $Research, $ResearchFromL3, $ResumeL3, $ExternalResearch, $ResumeL4, $UploadDocumentsL3).Where({ $_ }).Count -gt 1) {
    throw 'Choose only one run action.'
}
if (($DomainPlugin -or $Requirements) -and ($Resume -or $Research -or $ResearchFromL3 -or $ResumeL3 -or $ExternalResearch -or $ResumeL4 -or $UploadDocumentsL3)) {
    throw '-DomainPlugin and -Requirements apply only to new Layer 2 runs.'
}

function Invoke-Layer3([string[]]$Arguments) {
    # Research checkpoints require Docker; historical preparation-only actions retain Windows behavior.
    $NeedsDocker = [bool]($Research -or $ResearchFromL3)
    if ($ResumeL3) {
        $Existing = Get-Content -LiteralPath (Join-Path $ResumeL3 'run.json') -Raw | ConvertFrom-Json
        $NeedsDocker = [bool]$Existing.research
    }
    if (-not $NeedsDocker) {
        if (-not (Test-Path -LiteralPath $Python)) { throw "Required compute interpreter not found: $Python" }
        & $Python -m ML.deep_research.layer3 @Arguments
        return
    }
    $DockerCommand = Get-Command docker -ErrorAction SilentlyContinue
    $DockerExe = if ($DockerCommand) { $DockerCommand.Source } else {
        Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
    }
    if (-not (Test-Path -LiteralPath $DockerExe)) {
        throw 'Docker CLI unavailable. Run the Layer 3 command in the shared Dev Container.'
    }
    $Converted = @($Arguments)
    for ($Index = 1; $Index -lt $Converted.Count; $Index++) {
        if ($Converted[$Index - 1] -in @('--research', '--research-from', '--resume-l3', '--source-suggestion', '--research-instruction')) {
            $Resolved = [IO.Path]::GetFullPath($Converted[$Index], $ProjectDir)
            $Relative = [IO.Path]::GetRelativePath($ProjectDir, $Resolved)
            if ($Relative -eq '..' -or $Relative.StartsWith('..\') -or [IO.Path]::IsPathRooted($Relative)) {
                throw 'Docker Layer 3 inputs must be inside the shared project.'
            }
            $Converted[$Index] = '/app/' + $Relative.Replace('\', '/')
        }
    }
    & $DockerExe compose exec -T dev /usr/local/bin/python -m ML.deep_research.layer3 @Converted
}

if ($Research -or $ResearchFromL3) {
    $Layer3Args = if ($ResearchFromL3) { @('--research-from', $ResearchFromL3) } else { @('--research', $Research) }
    $Layer3Args += @('--research-reasoning-effort', $ResearchReasoningEffort)
    if ($SourceSuggestion) {
        $Layer3Args += @('--source-suggestion', $SourceSuggestion)
    }
    if ($ResearchInstruction) {
        $Layer3Args += @('--research-instruction', $ResearchInstruction)
    }
    if ($Online) {
        $Layer3Args += '--online'
    }
    if ($PublicInputConfirmed) {
        $Layer3Args += '--public-input-confirmed'
    }
    Invoke-Layer3 $Layer3Args
} elseif ($ExternalResearch) {
    $Layer4Args = @('--external-research', $ExternalResearch, '--online', '--public-input-confirmed')
    & $Python -m ML.deep_research.layer4 @Layer4Args
} elseif ($ResumeL3 -or $UploadDocumentsL3) {
    $Layer3Args = if ($UploadDocumentsL3) { @('--upload-documents', $UploadDocumentsL3) } else { @('--resume-l3', $ResumeL3) }
    if ($RetryFailed) {
        $Layer3Args += '--retry-failed'
    }
    Invoke-Layer3 $Layer3Args
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
    if (-not $PublicInputConfirmed) {
        throw 'Layer 2 web-assisted domain design requires -PublicInputConfirmed.'
    }
    & $Python -m ML.deep_research.layer2 $FactSheet --domain-plugin $DomainPlugin --requirements $Requirements --web-search-depth $Layer2WebSearchDepth --web-search-verbosity $Layer2WebSearchVerbosity --public-input-confirmed
}

exit $LASTEXITCODE
