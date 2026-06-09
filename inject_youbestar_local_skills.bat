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
$DefaultLocalRuntimeRoot = "D:\YoubestarLocal"

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

function Select-YoubestarProjectRoot {
    param([string]$InitialDirectory)
    $message = "Select the Youbestar project root folder. It must contain server.py and agent_system\skills\registry.json."

    try {
        $shell = New-Object -ComObject Shell.Application
        $folder = $shell.BrowseForFolder(0, $message, 0, $InitialDirectory)
        if ($null -ne $folder) {
            return $folder.Self.Path
        }
    } catch {
        Write-Warning "Folder picker failed: $($_.Exception.Message)"
    }

    $typedPath = Read-Host "Enter Youbestar project root path, or press Enter to cancel"
    if ([string]::IsNullOrWhiteSpace($typedPath)) {
        throw "Project root selection cancelled."
    }
    return $typedPath
}

function Resolve-YoubestarProject {
    $starts = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($env:PROJECT_ROOT_ARG)) {
        $starts.Add($env:PROJECT_ROOT_ARG)
    }
    if (-not [string]::IsNullOrWhiteSpace($env:YOUBESTAR_HOME)) {
        $starts.Add($env:YOUBESTAR_HOME)
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

    $initialDirectory = Search-UpForProject (Get-Location).Path
    if ([string]::IsNullOrWhiteSpace($initialDirectory)) {
        $initialDirectory = (Get-Location).Path
    }

    $selected = Select-YoubestarProjectRoot $initialDirectory
    $foundSelected = Search-UpForProject $selected
    if ($null -ne $foundSelected) {
        return $foundSelected
    }

    throw "Selected path is not a Youbestar project root. Choose the folder that contains server.py and agent_system\skills\registry.json."
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

function Resolve-LocalRuntimeRoot {
    if (-not [string]::IsNullOrWhiteSpace($env:YOUBESTAR_LOCAL_HOME)) {
        return [System.IO.Path]::GetFullPath($env:YOUBESTAR_LOCAL_HOME)
    }
    if (-not [string]::IsNullOrWhiteSpace($env:YOUBESTAR_LOCAL_DIR)) {
        return [System.IO.Path]::GetFullPath($env:YOUBESTAR_LOCAL_DIR)
    }
    return [System.IO.Path]::GetFullPath($DefaultLocalRuntimeRoot)
}

function Ensure-LocalRuntime {
    param([string]$Root)
    foreach ($relative in @("", "data", "skills\local", "registries", "imports", "backups", "logs")) {
        New-Item -ItemType Directory -Force -Path (Join-Path $Root $relative) | Out-Null
    }
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
    $destinationFull = [System.IO.Path]::GetFullPath($Destination).TrimEnd([char[]]@("\", "/"))
    if ($sourceFull.Equals($destinationFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return
    }
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

function Write-Utf8NoBom {
    param(
        [string]$Path,
        [string]$Content
    )
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Write-JsonObject {
    param(
        [object]$Value,
        [string]$Path
    )
    $json = $Value | ConvertTo-Json -Depth 80
    Write-Utf8NoBom -Path $Path -Content ($json + [Environment]::NewLine)
}

function Find-ManifestRoot {
    param([string]$Root)
    if (Test-Path -LiteralPath (Join-Path $Root "manifest.json")) {
        return $Root
    }
    if ((Test-Path -LiteralPath (Join-Path $Root "registries\local.registry.json")) -or
        (Test-Path -LiteralPath (Join-Path $Root "agent_system\skills\registry.local.json"))) {
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
            if (Test-Path -LiteralPath (Join-Path $root "manifest.json")) {
                return $root
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

function First-ExistingPath {
    param([string[]]$Paths)
    foreach ($path in $Paths) {
        if (-not [string]::IsNullOrWhiteSpace($path) -and (Test-Path -LiteralPath $path)) {
            return $path
        }
    }
    return $null
}

function Copy-FirstExistingTree {
    param(
        [string[]]$Sources,
        [string]$Destination
    )
    $source = First-ExistingPath $Sources
    if ($null -ne $source) {
        Copy-FilteredTree $source $Destination
    }
}

function ConvertTo-LocalRuntimeSkillPath {
    param(
        [string]$SkillName,
        [object]$Record
    )
    $simpleName = ($SkillName.Split(".") | Select-Object -Last 1) + ".py"
    $rawPath = ""
    if ($null -ne $Record -and $null -ne $Record.PSObject.Properties["path"]) {
        $rawPath = [string]$Record.path
    }
    $path = $rawPath.Replace("\", "/")
    if ([string]::IsNullOrWhiteSpace($path)) {
        return "skills/local/$simpleName"
    }
    if ($path.StartsWith("skills/local/", [System.StringComparison]::OrdinalIgnoreCase)) {
        return $path
    }
    if ($path.StartsWith("agent_system/skills/local/", [System.StringComparison]::OrdinalIgnoreCase)) {
        return "skills/local/" + $path.Substring("agent_system/skills/local/".Length)
    }
    if ([System.IO.Path]::IsPathRooted($rawPath)) {
        return "skills/local/" + [System.IO.Path]::GetFileName($rawPath)
    }
    return $path
}

function Copy-JsonRecord {
    param([object]$Record)
    $result = [ordered]@{}
    if ($null -ne $Record) {
        foreach ($prop in $Record.PSObject.Properties) {
            $result[$prop.Name] = $prop.Value
        }
    }
    return $result
}

$projectRoot = Resolve-YoubestarProject
$bundleRoot = Resolve-Bundle
$localRuntimeRoot = Resolve-LocalRuntimeRoot
Ensure-LocalRuntime $localRuntimeRoot
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $localRuntimeRoot ("backups\import_" + $stamp)
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$backupItems = @(
    "skills\local",
    "registries",
    "data"
)
foreach ($item in $backupItems) {
    $source = Join-Path $localRuntimeRoot $item
    if (Test-Path -LiteralPath $source) {
        $dest = Join-Path $backupRoot $item
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
        Copy-Item -LiteralPath $source -Destination $dest -Recurse -Force
    }
}

Copy-FirstExistingTree @(
    (Join-Path $bundleRoot "skills\local"),
    (Join-Path $bundleRoot "agent_system\skills\local")
) (Join-Path $localRuntimeRoot "skills\local")
Copy-FirstExistingTree @(
    (Join-Path $bundleRoot "data")
) (Join-Path $localRuntimeRoot "data")

Copy-Item -LiteralPath $env:BAT_PATH -Destination (Join-Path $localRuntimeRoot "inject_youbestar_local_skills.bat") -Force
$packScript = First-ExistingPath @(
    (Join-Path $bundleRoot "pack_youbestar_local_skills.bat"),
    (Join-Path $projectRoot "pack_youbestar_local_skills.bat"),
    (Join-Path $env:BAT_DIR "pack_youbestar_local_skills.bat")
)
if ($null -ne $packScript) {
    Copy-Item -LiteralPath $packScript -Destination (Join-Path $localRuntimeRoot "pack_youbestar_local_skills.bat") -Force
}

$targetRegistryPath = Join-Path $localRuntimeRoot "registries\local.registry.json"
$targetRegistry = Read-JsonObject $targetRegistryPath
$incomingRegistryPath = First-ExistingPath @(
    (Join-Path $bundleRoot "registries\local.registry.json"),
    (Join-Path $bundleRoot "agent_system\skills\registry.local.json")
)
$incomingRegistry = Read-JsonObject $incomingRegistryPath
foreach ($key in $incomingRegistry.Keys) {
    if ($key.StartsWith("local.")) {
        $record = Copy-JsonRecord $incomingRegistry[$key]
        $record["source"] = "local"
        $record["path"] = ConvertTo-LocalRuntimeSkillPath $key $incomingRegistry[$key]
        $targetRegistry[$key] = $record
    }
}
Write-JsonObject $targetRegistry $targetRegistryPath

$targetSettingsPath = Join-Path $localRuntimeRoot "registries\skill_settings.local.json"
$targetSettings = Read-JsonObject $targetSettingsPath
$incomingSettingsPath = First-ExistingPath @(
    (Join-Path $bundleRoot "registries\skill_settings.local.json"),
    (Join-Path $bundleRoot "agent_system\skill_settings.local.json")
)
$incomingSettings = Read-JsonObject $incomingSettingsPath
foreach ($key in $incomingSettings.Keys) {
    if ($key.StartsWith("local.")) {
        $targetSettings[$key] = $incomingSettings[$key]
    }
}
Write-JsonObject $targetSettings $targetSettingsPath

Write-Host ""
Write-Host "Youbestar local agent bundle injected."
Write-Host "Project      : $projectRoot"
Write-Host "Local runtime: $localRuntimeRoot"
Write-Host "Bundle       : $bundleRoot"
Write-Host "Backup       : $backupRoot"
Write-Host ""
Write-Host "Restart Youbestar if it is already running, then open the Skills page to confirm local skills."
