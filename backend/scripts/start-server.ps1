param(
    [string]$Config = (Join-Path $PSScriptRoot 'server.env.ps1'),
    [string]$HostName = '127.0.0.1',
    [int]$Port = 8000
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Config -PathType Leaf)) {
    throw "找不到服务配置：$Config。请按 server.env.example.ps1 创建私有配置。"
}
. (Resolve-Path -LiteralPath $Config).Path
$exe = Join-Path $PSScriptRoot 'LungTic-Server.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "找不到服务程序：$exe" }
& $exe --host $HostName --port $Port
exit $LASTEXITCODE
