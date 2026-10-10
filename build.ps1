param([string]$EnvironmentPath = "$PSScriptRoot/.conda-env")
$ErrorActionPreference = 'Stop'
$pythonExe = Join-Path $EnvironmentPath 'python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw '请先使用 mamba env create -p .conda-env -f environment.yml 创建环境。'
}
Push-Location $PSScriptRoot
$previousPath = $env:PATH
$previousPythonPath = $env:PYTHONPATH
$env:PATH = "$EnvironmentPath/Library/bin;$env:PATH"
$env:PYTHONPATH = "$PSScriptRoot/src"
try {
    & $pythonExe -m unittest discover -s tests -t . -v
    if ($LASTEXITCODE -ne 0) { throw '测试未通过，停止打包。' }
    & $pythonExe -m PyInstaller --noconfirm --clean --onefile --windowed --paths src --collect-data a2l_hex_calibrator --name A2LHexCalibrator --distpath dist --workpath build app.py
    if ($LASTEXITCODE -ne 0) { throw 'EXE 打包失败。' }
} finally {
    $env:PATH = $previousPath
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
