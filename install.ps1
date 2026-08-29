# Install DJI Clip Color into DaVinci Resolve's Utility scripts folder.
# From a clone / ZIP:  Right-click install.bat  or  powershell -File install.ps1
# From the web:
#   irm https://raw.githubusercontent.com/erik-sutton95/dji-clip-color/main/install.ps1 | iex

$ErrorActionPreference = "Stop"
$RepoSlug = if ($env:DJI_CLIP_COLOR_REPO) { $env:DJI_CLIP_COLOR_REPO } else { "erik-sutton95/dji-clip-color" }
$Branch = if ($env:DJI_CLIP_COLOR_BRANCH) { $env:DJI_CLIP_COLOR_BRANCH } else { "main" }
$RawUrl = "https://raw.githubusercontent.com/$RepoSlug/$Branch/dji_clip_color.py"
$ScriptName = "DJI Clip Color.py"
$Dest = Join-Path $env:APPDATA "Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"

function Pause-IfInteractive {
    if ($Host.Name -eq "ConsoleHost" -and [Environment]::UserInteractive -and -not $env:DJI_CLIP_COLOR_NOPAUSE) {
        Write-Host ""
        Read-Host "Press Enter to close"
    }
}

Write-Host ""
Write-Host "DJI Clip Color - installer"
Write-Host "=========================="

$here = $null
if ($PSScriptRoot) { $here = $PSScriptRoot }
elseif ($MyInvocation.MyCommand.Path) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }

$src = $null
if ($here) {
    $local = Join-Path $here "dji_clip_color.py"
    if (Test-Path $local) { $src = $local }
}

$temp = $null
try {
    if (-not $src) {
        Write-Host "No local dji_clip_color.py - downloading from GitHub ($RepoSlug@$Branch)"
        $temp = Join-Path ([System.IO.Path]::GetTempPath()) ("dji_clip_color_" + [guid]::NewGuid().ToString() + ".py")
        Invoke-WebRequest -Uri $RawUrl -OutFile $temp -UseBasicParsing
        $src = $temp
    }

    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    Copy-Item -Force $src (Join-Path $Dest $ScriptName)

    Write-Host ""
    Write-Host "Installed:"
    Write-Host "  $(Join-Path $Dest $ScriptName)"

    $resolve = Join-Path ${env:ProgramFiles} "Blackmagic Design\DaVinci Resolve\Resolve.exe"
    if (Test-Path $resolve) {
        Write-Host ""
        Write-Host "DaVinci Resolve found."
    } else {
        Write-Host ""
        Write-Host "Note: Resolve.exe was not in Program Files. The script is still installed."
    }

    Write-Host ""
    Write-Host "Next:"
    Write-Host "  1. Restart DaVinci Resolve if it is already open."
    Write-Host "  2. Import original MP4 / MOV takes (not .LRF / .XRF proxies)."
    Write-Host "  3. Select clips in the Media Pool."
    Write-Host "  4. Workspace > Scripts > DJI Clip Color"
    Write-Host "  5. Customize Columns: add Color Space Notes or Keywords (search notes / keyword)."
    Write-Host ""
    Write-Host "Clip colors:  Orange = D-Log2   Navy = D-Log   Pink = D-Log M   Teal = HLG"

    if (Get-Command explorer.exe -ErrorAction SilentlyContinue) {
        Start-Process explorer.exe -ArgumentList "/select,`"$Dest\$ScriptName`""
    }
} catch {
    Write-Host "Error: $($_.Exception.Message)"
    Pause-IfInteractive
    exit 1
} finally {
    if ($temp -and (Test-Path $temp)) { Remove-Item -Force $temp }
}

Pause-IfInteractive
