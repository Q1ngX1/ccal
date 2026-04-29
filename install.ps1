[CmdletBinding()]
param(
    [string]$Repository = $(if ($env:CCAL_REPO) { $env:CCAL_REPO } else { 'Q1ngX1/ccal' }),
    [string]$Version = $(if ($env:CCAL_VERSION) { $env:CCAL_VERSION } else { 'latest' }),
    [string]$InstallDir = $(if ($env:CCAL_INSTALL_DIR) { $env:CCAL_INSTALL_DIR } else { '' }),
    [string]$TesseractHome = $(if ($env:CCAL_TESSERACT_HOME) { $env:CCAL_TESSERACT_HOME } else { '' }),
    [string]$TesseractCmd = $(if ($env:CCAL_TESSERACT_CMD) { $env:CCAL_TESSERACT_CMD } else { '' }),
    [switch]$NoPathUpdate,
    [switch]$VerifyInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Fail([string]$Message) {
    throw "install.ps1: $Message"
}

function Get-Release([string]$Repo, [string]$Tag) {
    $headers = @{ Accept = 'application/vnd.github+json' }
    if ($env:CCAL_GITHUB_TOKEN) {
        $headers.Authorization = "Bearer $env:CCAL_GITHUB_TOKEN"
    }

    if ($Tag -eq 'latest') {
        return Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$Repo/releases/latest"
    }

    $normalizedTag = if ($Tag.StartsWith('v')) { $Tag } else { "v$Tag" }
    return Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$Repo/releases/tags/$normalizedTag"
}

function Get-Architecture {
    switch ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()) {
        'x64' { return 'x64' }
        'arm64' { return 'arm64' }
        default { Fail "unsupported architecture: $([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture)" }
    }
}

function Get-AssetCandidates([string]$Arch, [string]$VersionTag) {
    $version = if ($VersionTag.StartsWith('v')) { $VersionTag } else { "v$VersionTag" }
    $versionPrefix = "ccal-$version-windows"
    if ($Arch -eq 'arm64') {
        return @(
            "$versionPrefix-arm64.exe",
            "$versionPrefix-arm64",
            'ccal-windows-arm64.exe',
            'ccal-windows-arm64'
        )
    }
    return @(
        "$versionPrefix-x64.exe",
        "$versionPrefix-x64",
        "$versionPrefix-x86_64.exe",
        "$versionPrefix-x86_64",
        'ccal-windows-x64.exe',
        'ccal-windows-x64',
        'ccal-windows-x86_64.exe',
        'ccal-windows-x86_64'
    )
}

function Select-Asset([object[]]$Assets, [string[]]$Candidates) {
    foreach ($candidate in $Candidates) {
        $asset = $Assets | Where-Object { $_.name -eq $candidate } | Select-Object -First 1
        if ($asset) {
            return $asset
        }
    }
    return $null
}

function Get-DefaultInstallDir {
    $localAppData = [Environment]::GetFolderPath('LocalApplicationData')
    if ([string]::IsNullOrWhiteSpace($localAppData)) {
        return Join-Path $HOME 'AppData\Local\Programs\ccal'
    }
    return Join-Path $localAppData 'Programs\ccal'
}

function Add-ToUserPath([string]$Directory) {
    $current = [Environment]::GetEnvironmentVariable('Path', 'User')
    $parts = @()
    if ($current) {
        $parts = $current -split ';' | Where-Object { $_ -and $_.Trim() }
    }

    if ($parts -notcontains $Directory) {
        [Environment]::SetEnvironmentVariable('Path', (@($parts + $Directory) -join ';'), 'User')
    }

    $env:Path = "$Directory;$env:Path"
}

function Resolve-TesseractCommand {
    param([string]$TesseractHome, [string]$TesseractCmd)

    if ($TesseractCmd) {
        if (Test-Path $TesseractCmd) {
            return (Resolve-Path $TesseractCmd).Path
        }
        Fail "Tesseract command not found: $TesseractCmd"
    }

    if ($TesseractHome) {
        foreach ($candidate in @(
            (Join-Path $TesseractHome 'tesseract.exe'),
            (Join-Path $TesseractHome 'bin\tesseract.exe'),
            (Join-Path $TesseractHome 'tesseract\tesseract.exe')
        )) {
            if (Test-Path $candidate) {
                return (Resolve-Path $candidate).Path
            }
        }
        Fail "Tesseract executable not found under $TesseractHome"
    }

    return $null
}

function Configure-TesseractRuntime {
    param([string]$TesseractHome, [string]$TesseractCmd)

    $resolvedCmd = Resolve-TesseractCommand -TesseractHome $TesseractHome -TesseractCmd $TesseractCmd
    if (-not $resolvedCmd) {
        return
    }

    $resolvedHome = Split-Path -Parent $resolvedCmd
    [Environment]::SetEnvironmentVariable('CCAL_TESSERACT_CMD', $resolvedCmd, 'User')
    [Environment]::SetEnvironmentVariable('CCAL_TESSERACT_HOME', $resolvedHome, 'User')
    $env:CCAL_TESSERACT_CMD = $resolvedCmd
    $env:CCAL_TESSERACT_HOME = $resolvedHome
}

$release = Get-Release -Repo $Repository -Tag $Version
$arch = Get-Architecture
$asset = Select-Asset -Assets $release.assets -Candidates (Get-AssetCandidates -Arch $arch -VersionTag $release.tag_name)
if (-not $asset) {
    Fail "could not find a Windows release asset for $arch"
}

$installDir = if ($InstallDir) { $InstallDir } else { Get-DefaultInstallDir }
$targetPath = Join-Path $installDir 'ccal.exe'
$tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("ccal-install-{0}" -f ([guid]::NewGuid().ToString('N')))
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

try {
    $downloadPath = Join-Path $tmpDir $asset.name
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $downloadPath
    Copy-Item -Force $downloadPath $targetPath

    if (-not $NoPathUpdate) {
        Add-ToUserPath -Directory $installDir
    }

    Configure-TesseractRuntime -TesseractHome $TesseractHome -TesseractCmd $TesseractCmd

    Write-Host "Installed ccal to $targetPath"
    if ($TesseractHome -or $TesseractCmd) {
        Write-Host "Configured Tesseract runtime."
    }

    if ($VerifyInstall) {
        & $targetPath --version | Select-Object -First 1
    }
}
finally {
    Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
}
