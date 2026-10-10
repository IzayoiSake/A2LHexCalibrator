param([string]$EnvironmentPath = "$(Split-Path $PSScriptRoot -Parent)/.conda-env")
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$previousPath = $env:PATH
$previousPythonPath = $env:PYTHONPATH
Push-Location $projectRoot
try {
    $env:PATH = "$EnvironmentPath/Library/bin;$env:PATH"
    $env:PYTHONPATH = "$projectRoot/src"
    & "$EnvironmentPath/python.exe" -m unittest discover -s tests -t . -v
    if ($LASTEXITCODE -ne 0) { throw '回归测试失败。' }
} finally {
    $env:PATH = $previousPath
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
