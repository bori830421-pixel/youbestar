@echo off
setlocal
set "BUNDLE_ARG=%~1"
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
    if (-not (Test-Path -LiteralPath $Source)) {
        return
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
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

function Find-ManifestRoot {
    param([string]$Root)
    if (Test-Path -LiteralPath (Join-Path $Root "manifest.json")) {
        return $Root
    }
    $manifest = Get-ChildItem -LiteralPath $Root -Filter "manifest.json" -Recurse -File -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $manifest) {
        return $null
    }
    return $manifest.Directory.FullName
}

function Resolve-Bundle {
    $candidates = New-Object System.Collections.Generic.List[System.IO.FileSystemInfo]
    if (-not [string]::IsNullOrWhiteSpace($env:BUNDLE_ARG)) {
        $path = if ([System.IO.Path]::IsPathRooted($env:BUNDLE_ARG)) {
            [System.IO.Path]::GetFullPath($env:BUNDLE_ARG)
        } else {
            [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $env:BUNDLE_ARG))
        }
        $item = Get-Item -LiteralPath $path -ErrorAction Stop
        $candidates.Add($item)
    } else {
        foreach ($root in @($env:BAT_DIR, (Get-Location).Path)) {
            if ([string]::IsNullOrWhiteSpace($root) -or -not (Test-Path -LiteralPath $root)) {
                continue
            }
            Get-ChildItem -LiteralPath $root -Directory -Filter "youbestar_local_skills_bundle*" -ErrorAction SilentlyContinue |
                ForEach-Object { $candidates.Add($_) }
            Get-ChildItem -LiteralPath $root -File -Filter "youbestar_local_skills_bundle*.zip" -ErrorAction SilentlyContinue |
                ForEach-Object { $candidates.Add($_) }
        }
    }

    $candidate = $candidates |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $candidate) {
        throw "Cannot find a bundle. Put the bundle next to this BAT file, or pass bundle folder/zip as the first argument."
    }

    if (-not $candidate.PSIsContainer -and $candidate.Extension.ToLowerInvariant() -eq ".zip") {
        $extractRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("youbestar_local_skills_import_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
        New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null
        Expand-Archive -LiteralPath $candidate.FullName -DestinationPath $extractRoot -Force
        $manifestRoot = Find-ManifestRoot $extractRoot
        if ($null -eq $manifestRoot) {
            throw "The zip does not contain manifest.json."
        }
        return $manifestRoot
    }

    $folderRoot = Find-ManifestRoot $candidate.FullName
    if ($null -eq $folderRoot) {
        throw "The bundle folder does not contain manifest.json."
    }
    return $folderRoot
}

$projectRoot = Resolve-YoubestarProject
$bundleRoot = Resolve-Bundle
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $projectRoot ("agent_system\import_backups\" + $stamp)
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$backupItems = @(
    "agent_system\skills\local",
    "agent_system\skills\registry.json",
    "agent_system\skill_settings.json",
    "tools",
    "data"
)
foreach ($item in $backupItems) {
    $source = Join-Path $projectRoot $item
    if (Test-Path -LiteralPath $source) {
        $dest = Join-Path $backupRoot $item
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
        Copy-Item -LiteralPath $source -Destination $dest -Recurse -Force
    }
}

Copy-FilteredTree (Join-Path $bundleRoot "agent_system\skills\local") (Join-Path $projectRoot "agent_system\skills\local")
Copy-FilteredTree (Join-Path $bundleRoot "tools") (Join-Path $projectRoot "tools")
Copy-FilteredTree (Join-Path $bundleRoot "data") (Join-Path $projectRoot "data")

$targetRegistryPath = Join-Path $projectRoot "agent_system\skills\registry.json"
$targetRegistry = Read-JsonObject $targetRegistryPath
$incomingRegistry = Read-JsonObject (Join-Path $bundleRoot "agent_system\skills\registry.local.json")
foreach ($key in $incomingRegistry.Keys) {
    if ($key.StartsWith("local.")) {
        $targetRegistry[$key] = $incomingRegistry[$key]
    }
}
Write-JsonObject $targetRegistry $targetRegistryPath

$targetSettingsPath = Join-Path $projectRoot "agent_system\skill_settings.json"
$targetSettings = Read-JsonObject $targetSettingsPath
$incomingSettings = Read-JsonObject (Join-Path $bundleRoot "agent_system\skill_settings.local.json")
foreach ($key in $incomingSettings.Keys) {
    if ($key.StartsWith("local.")) {
        $targetSettings[$key] = $incomingSettings[$key]
    }
}
Write-JsonObject $targetSettings $targetSettingsPath

Write-Host ""
Write-Host "Youbestar local agent bundle injected."
Write-Host "Project: $projectRoot"
Write-Host "Bundle : $bundleRoot"
Write-Host "Backup : $backupRoot"
Write-Host ""
Write-Host "Restart Youbestar if it is already running, then open the Skills page to confirm local skills."
