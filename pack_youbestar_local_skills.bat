@echo off
setlocal
set "PACK_DEST=%~1"
set "PROJECT_ROOT_ARG=%~2"
set "BAT_PATH=%~f0"
set "BAT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $raw=Get-Content -Raw -Encoding UTF8 -LiteralPath $env:BAT_PATH; $marker='# POWERSHELL'; $idx=$raw.LastIndexOf($marker); if ($idx -lt 0) { throw 'PowerShell payload marker not found.' }; $script=$raw.Substring($idx + $marker.Length); & ([scriptblock]::Create($script))"
exit /b %ERRORLEVEL%
# POWERSHELL

$DeniedDirs = @(
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "build",
    "dist",
    "node_modules",
    "runtime"
)
$DeniedFileRegex = "(?i)(^\.env|^youbestar\.json$|token|cookie|credential|secret|password|passwd|private[_-]?key|api[_-]?key|auth)"

function Test-ProjectRoot {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }
    $full = [System.IO.Path]::GetFullPath($Path)
    return (Test-Path -LiteralPath (Join-Path $full "server.py")) -and
        (Test-Path -LiteralPath (Join-Path $full "agent_system\skills\registry.json"))
}

function Search-UpForProject {
    param([string]$Start)
    if ([string]::IsNullOrWhiteSpace($Start)) {
        return $null
    }
    $item = Get-Item -LiteralPath $Start -ErrorAction SilentlyContinue
    if ($null -eq $item) {
        return $null
    }
    if (-not $item.PSIsContainer) {
        $item = $item.Directory
    }
    while ($null -ne $item) {
        if (Test-ProjectRoot $item.FullName) {
            return $item.FullName
        }
        $parent = $item.Parent
        if ($null -eq $parent -or $parent.FullName -eq $item.FullName) {
            break
        }
        $item = $parent
    }
    return $null
}

function Resolve-YoubestarProject {
    $starts = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($env:PROJECT_ROOT_ARG)) {
        $starts.Add($env:PROJECT_ROOT_ARG)
    }
    if (-not [string]::IsNullOrWhiteSpace($env:YOUBESTAR_HOME)) {
        $starts.Add($env:YOUBESTAR_HOME)
    }
    $starts.Add((Get-Location).Path)
    $starts.Add($env:BAT_DIR)
    $starts.Add("D:\codex_projects\youbestar")
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        $starts.Add((Join-Path $env:USERPROFILE "codex_projects\youbestar"))
    }

    $seen = @{}
    foreach ($start in $starts) {
        if ([string]::IsNullOrWhiteSpace($start)) {
            continue
        }
        $full = [System.IO.Path]::GetFullPath($start)
        if ($seen.ContainsKey($full)) {
            continue
        }
        $seen[$full] = $true
        $found = Search-UpForProject $full
        if ($null -ne $found) {
            return $found
        }
    }

    throw "Cannot find Youbestar project. Set YOUBESTAR_HOME or pass project root as the second argument."
}

function Resolve-OutputRoot {
    if ([string]::IsNullOrWhiteSpace($env:PACK_DEST)) {
        return [System.IO.Path]::GetFullPath($env:BAT_DIR)
    }
    if ([System.IO.Path]::IsPathRooted($env:PACK_DEST)) {
        return [System.IO.Path]::GetFullPath($env:PACK_DEST)
    }
    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $env:PACK_DEST))
}

function Test-SkipItem {
    param([System.IO.FileSystemInfo]$Item)
    $parts = $Item.FullName -split "[\\/]"
    foreach ($part in $parts) {
        if ($DeniedDirs -contains $part.ToLowerInvariant()) {
            return $true
        }
    }
    if (-not $Item.PSIsContainer) {
        $name = $Item.Name
        if ($name -match $DeniedFileRegex) {
            return $true
        }
        $lower = $name.ToLowerInvariant()
        if ($lower.EndsWith(".pyc") -or $lower.EndsWith(".pyo")) {
            return $true
        }
    }
    return $false
}

function Copy-FilteredTree {
    param(
        [string]$Source,
        [string]$Destination
    )
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    if (-not (Test-Path -LiteralPath $Source)) {
        return
    }
    $sourceFull = (Resolve-Path -LiteralPath $Source).Path.TrimEnd([char[]]@("\", "/"))
    Get-ChildItem -LiteralPath $sourceFull -Recurse -Force | ForEach-Object {
        if (Test-SkipItem $_) {
            return
        }
        $relative = $_.FullName.Substring($sourceFull.Length).TrimStart([char[]]@("\", "/"))
        $target = Join-Path $Destination $relative
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Force -Path $target | Out-Null
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
        }
    }
}

function Read-JsonObject {
    param([string]$Path)
    $result = [ordered]@{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $result
    }
    $raw = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return $result
    }
    $obj = $raw | ConvertFrom-Json
    foreach ($prop in $obj.PSObject.Properties) {
        $result[$prop.Name] = $prop.Value
    }
    return $result
}

function Write-JsonObject {
    param(
        [object]$Value,
        [string]$Path
    )
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
    $Value | ConvertTo-Json -Depth 80 | Set-Content -LiteralPath $Path -Encoding UTF8
}

$projectRoot = Resolve-YoubestarProject
$outputRoot = Resolve-OutputRoot
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$bundleName = "youbestar_local_skills_bundle_$stamp"
$bundleDir = Join-Path $outputRoot $bundleName
$zipPath = "$bundleDir.zip"

New-Item -ItemType Directory -Force -Path $bundleDir | Out-Null

Copy-FilteredTree (Join-Path $projectRoot "agent_system\skills\local") (Join-Path $bundleDir "agent_system\skills\local")
Copy-FilteredTree (Join-Path $projectRoot "tools") (Join-Path $bundleDir "tools")
Copy-FilteredTree (Join-Path $projectRoot "data") (Join-Path $bundleDir "data")

$packScript = Join-Path $projectRoot "pack_youbestar_local_skills.bat"
$injectScript = Join-Path $projectRoot "inject_youbestar_local_skills.bat"
if (Test-Path -LiteralPath $packScript) {
    Copy-Item -LiteralPath $packScript -Destination (Join-Path $bundleDir "pack_youbestar_local_skills.bat") -Force
}
if (Test-Path -LiteralPath $injectScript) {
    Copy-Item -LiteralPath $injectScript -Destination (Join-Path $bundleDir "inject_youbestar_local_skills.bat") -Force
}

$registry = Read-JsonObject (Join-Path $projectRoot "agent_system\skills\registry.json")
$localRegistry = [ordered]@{}
foreach ($key in $registry.Keys) {
    $record = $registry[$key]
    $source = ""
    if ($null -ne $record -and $null -ne $record.PSObject.Properties["source"]) {
        $source = [string]$record.source
    }
    if ($key.StartsWith("local.") -or $source -eq "local") {
        $localRegistry[$key] = $record
    }
}
Write-JsonObject $localRegistry (Join-Path $bundleDir "agent_system\skills\registry.local.json")

$settings = Read-JsonObject (Join-Path $projectRoot "agent_system\skill_settings.json")
$localSettings = [ordered]@{}
foreach ($key in $settings.Keys) {
    if ($key.StartsWith("local.")) {
        $localSettings[$key] = $settings[$key]
    }
}
Write-JsonObject $localSettings (Join-Path $bundleDir "agent_system\skill_settings.local.json")

$manifest = [ordered]@{
    package = "youbestar_local_skills_bundle"
    version = 1
    created_at = (Get-Date).ToString("s")
    source_project = $projectRoot
    includes = @(
        "agent_system\skills\local",
        "agent_system\skills\registry.local.json",
        "agent_system\skill_settings.local.json",
        "tools",
        "data",
        "pack_youbestar_local_skills.bat",
        "inject_youbestar_local_skills.bat"
    )
    excludes = @(
        "youbestar.json",
        ".env",
        ".git",
        ".venv",
        "token/cookie/credential/secret/password files"
    )
    warning = "This bundle may contain private business knowledge from data\. Keep it in a trusted private location."
}
Write-JsonObject $manifest (Join-Path $bundleDir "manifest.json")

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "Youbestar local agent bundle created."
Write-Host "Project : $projectRoot"
Write-Host "Folder  : $bundleDir"
Write-Host "Zip     : $zipPath"
Write-Host ""
Write-Host "Keep this package private. It includes local skills and data knowledge, but excludes config secrets."
Start-Process explorer.exe -ArgumentList "/select,`"$zipPath`""
