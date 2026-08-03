[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = (& git -C $PSScriptRoot rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $repositoryRoot) {
    throw "This script must be run from a clone of the AI Lecture System repository."
}

$hookPath = Join-Path $repositoryRoot ".githooks\pre-push"
if (-not (Test-Path -LiteralPath $hookPath -PathType Leaf)) {
    throw "Required hook not found: $hookPath"
}

& git -C $repositoryRoot config --local core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) {
    throw "Unable to configure core.hooksPath for this clone."
}

$configuredPath = (& git -C $repositoryRoot config --local --get core.hooksPath)
if ($LASTEXITCODE -ne 0 -or $configuredPath -ne ".githooks") {
    throw "Git hook configuration could not be verified."
}

Write-Output "Local Git safety hooks are active for: $repositoryRoot"
Write-Output "core.hooksPath=$configuredPath"
