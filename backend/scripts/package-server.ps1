param(
    [string]$BuildPython = $env:LUNGTIC_BUILD_PYTHON,
    [string]$OutputRoot = ''
)
$ErrorActionPreference = 'Stop'
$backendRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repoRoot = (Resolve-Path (Join-Path $backendRoot '..')).Path
if (-not $BuildPython) { $BuildPython = (Get-Command python -ErrorAction Stop).Source }
if (-not $OutputRoot) { $OutputRoot = Join-Path $repoRoot 'backend-dist' }
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$output = Join-Path $OutputRoot 'LungTic-Server'
if (Test-Path -LiteralPath $output) { throw "产物已存在，请先另存旧版或指定新的 OutputRoot：$output" }
$workRoot = [System.IO.Path]::GetFullPath((Join-Path $env:TEMP 'LungTic-server-build'))
$work = [System.IO.Path]::GetFullPath((Join-Path $workRoot ([guid]::NewGuid().ToString())))
try {
    New-Item -ItemType Directory -Path $OutputRoot,$work -Force | Out-Null
    $arguments = @(
        '--clean', '--onedir', '--console', '--noupx',
        '--name=LungTic-Server',
        "--distpath=$OutputRoot",
        "--workpath=$work",
        "--specpath=$work",
        "--paths=$backendRoot",
        '--hidden-import=onnxruntime',
        '--hidden-import=pymysql',
        '--hidden-import=sqlalchemy.dialects.mysql.pymysql',
        '--hidden-import=sqlalchemy.dialects.sqlite.pysqlite',
        '--hidden-import=passlib.handlers.bcrypt',
        '--hidden-import=uvicorn.protocols.http.h11_impl',
        '--hidden-import=uvicorn.loops.asyncio',
        '--hidden-import=uvicorn.lifespan.on',
        '--collect-all=onnxruntime',
        '--exclude-module=pytest',
        (Join-Path $backendRoot 'packaged_server.py')
    )
    & $BuildPython -m PyInstaller @arguments
    if ($LASTEXITCODE -ne 0) { throw '服务端封装失败' }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'start-server.ps1') -Destination $output
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'server.env.example.ps1') -Destination $output
    Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\CLINICAL_SERVER.md') -Destination $output
    Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\CLIENT_ADMIN_SPLIT.md') -Destination $output
    New-Item -ItemType Directory -Path (Join-Path $output 'database') -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $repoRoot 'database\schema.sql') -Destination (Join-Path $output 'database')
    Copy-Item -LiteralPath (Join-Path $repoRoot 'database\migrations') -Destination (Join-Path $output 'database') -Recurse
    Write-Host "服务端目录：$output"
} finally {
    $prefix = $workRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if ($work.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $work)) {
        Remove-Item -LiteralPath $work -Recurse -Force
    }
}
