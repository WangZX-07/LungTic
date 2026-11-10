param(
    [string]$PythonExe = "D:\envs\lungtic-training\python.exe"
)

$ErrorActionPreference = "Stop"
$frontendDir = Split-Path -Parent $PSScriptRoot
$uiDir = Split-Path -Parent $frontendDir
$backendDir = Join-Path $uiDir "backend"
$backendDist = Join-Path $uiDir "backend-dist"
$buildDir = Join-Path $uiDir "build\pyinstaller"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python environment not found: $PythonExe"
}

$pythonDir = Split-Path -Parent $PythonExe
$originalPath = $env:PATH
$env:PATH = @(
    $pythonDir
    (Join-Path $pythonDir "Library\bin")
    (Join-Path $pythonDir "DLLs")
    $originalPath
) -join ";"

New-Item -ItemType Directory -Force -Path (Join-Path $uiDir "build") | Out-Null
New-Item -ItemType Directory -Force -Path $backendDist | Out-Null

Push-Location $backendDir
try {
    & $PythonExe -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --name lungtic-viewer-backend `
        --distpath $backendDist `
        --workpath $buildDir `
        --specpath (Join-Path $uiDir "build") `
        --paths $uiDir `
        --collect-all h5py `
        --hidden-import uvicorn.logging `
        --hidden-import uvicorn.loops.auto `
        --hidden-import uvicorn.protocols.http.auto `
        --hidden-import uvicorn.protocols.websockets.auto `
        --hidden-import uvicorn.lifespan.on `
        --exclude-module torch `
        --exclude-module onnxruntime `
        --exclude-module cv2 `
        --exclude-module scipy `
        --exclude-module skimage `
        --exclude-module matplotlib `
        viewer_main.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
} finally {
    Pop-Location
    $env:PATH = $originalPath
}

Push-Location $frontendDir
try {
    npm run electron:build
    if ($LASTEXITCODE -ne 0) { throw "Electron build failed" }
} finally {
    Pop-Location
}

Write-Host "Installer created in: $(Join-Path $frontendDir 'release')"
