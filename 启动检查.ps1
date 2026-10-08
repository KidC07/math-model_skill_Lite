param(
    [string]$Python,
    [ValidateSet('check', 'smoke')][string]$Mode = 'check',
    [string]$Features = 'numerics,plot,excel,pdf,latex',
    [string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$checker = Join-Path $PSScriptRoot '.agents/skills/mathorcup-modeling/scripts/local_check.py'
$candidates = [System.Collections.Generic.List[string]]::new()
if ($Python) {
    $candidates.Add($Python)
} else {
    if ($env:MATHORCUP_PYTHON) { $candidates.Add($env:MATHORCUP_PYTHON) }
    $userProfilePath = [Environment]::GetFolderPath('UserProfile')
    $candidates.Add((Join-Path $userProfilePath '.local/share/math-modeling/venv/Scripts/python.exe'))
    $candidates.Add((Join-Path $PSScriptRoot '.venv/Scripts/python.exe'))
    if ($env:VIRTUAL_ENV) { $candidates.Add((Join-Path $env:VIRTUAL_ENV 'Scripts/python.exe')) }
    $hintFile = Join-Path $PSScriptRoot '本机环境.json'
    if (Test-Path -LiteralPath $hintFile) {
        $hints = Get-Content -LiteralPath $hintFile -Raw -Encoding utf8 | ConvertFrom-Json
        foreach ($item in $hints.python_candidates) { $candidates.Add([string]$item) }
    }
    $onPath = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($onPath -and $onPath.Source -notlike '*WindowsApps*') { $candidates.Add($onPath.Source) }
}
$selectedPython = $null
foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
    $probeArgs = @('-B', '-X', 'utf8', $checker, 'check', '--features', $Features, '--quiet')
    & $candidate @probeArgs
    $probeExit = $LASTEXITCODE
    if ($probeExit -eq 0) { $selectedPython = $candidate; break }
    if ($Python) {
        & $candidate '-B' '-X' 'utf8' $checker 'check' '--features' $Features
        exit $LASTEXITCODE
    }
}
if (-not $selectedPython) {
    Write-Error 'The existing environment lacks a requested capability (Python libraries or XeLaTeX). Run the quick check with your chosen Python for details; nothing was installed.'
    exit 2
}
Write-Host ('Selected existing Python: ' + $selectedPython)
$runArgs = @('-B', '-X', 'utf8', $checker, $Mode, '--features', $Features)
if ($Mode -eq 'smoke') {
    if (-not $OutputDirectory) { throw 'smoke requires -OutputDirectory with a new directory.' }
    $runArgs += @('--out', $OutputDirectory)
}
& $selectedPython @runArgs
exit $LASTEXITCODE
