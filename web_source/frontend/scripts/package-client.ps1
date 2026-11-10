$ErrorActionPreference = "Stop"
$frontendRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$stagingRoot = [System.IO.Path]::GetFullPath((Join-Path $env:TEMP "LungTic-client-build"))
$staging = [System.IO.Path]::GetFullPath((Join-Path $stagingRoot ([guid]::NewGuid().ToString())))
$output = Join-Path $frontendRoot "release-client"

try {
    Push-Location $frontendRoot
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }

    $electronDist = Join-Path $frontendRoot "node_modules\electron\dist"
    if (-not (Test-Path -LiteralPath (Join-Path $electronDist "electron.exe"))) {
        throw "Local Electron runtime is missing; run npm install first"
    }
    & ".\node_modules\.bin\electron-builder.cmd" --config electron-builder.client.json "--config.directories.output=$staging" "--config.electronDist=$electronDist" --win nsis
    if ($LASTEXITCODE -ne 0) { throw "Electron packaging failed" }

    $installer = Get-ChildItem -LiteralPath $staging -Filter "LungTic-Clinical-*-Setup.exe" -File |
        Select-Object -First 1
    if (-not $installer) { throw "Installer was not produced" }
    New-Item -ItemType Directory -Path $output -Force | Out-Null
    Copy-Item -LiteralPath $installer.FullName -Destination (Join-Path $output $installer.Name) -Force
    Write-Host "Installer: $(Join-Path $output $installer.Name)"
}
finally {
    Pop-Location
    $resolved = [System.IO.Path]::GetFullPath($staging)
    $prefix = $stagingRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if ($resolved.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolved)) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
