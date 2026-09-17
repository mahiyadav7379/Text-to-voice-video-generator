# FFmpeg Installation Script for Windows
# This script downloads and installs FFmpeg

Write-Host ""
Write-Host "============================================"
Write-Host "    FFmpeg Installation Script (PowerShell)"
Write-Host "============================================"
Write-Host ""

# Check if FFmpeg is already installed
try {
    $ffmpegVersion = & ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Host "[SUCCESS] FFmpeg is already installed!"
    Write-Host $ffmpegVersion
    exit
} catch {
    # Not installed, continue
}

Write-Host "[*] FFmpeg not found. Installing..."
Write-Host ""

# Create temp directory
$tempDir = "$env:TEMP\ffmpeg_install"
if (-not (Test-Path $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
}

# Download FFmpeg
$url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
$outputPath = "$tempDir\ffmpeg.zip"

Write-Host "[*] Downloading FFmpeg from GitHub..."
Write-Host "[*] This may take 1-2 minutes depending on your connection..."
Write-Host ""

try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $url -OutFile $outputPath -UseBasicParsing
    Write-Host "[SUCCESS] Download complete"
    Write-Host ""
} catch {
    Write-Host "[ERROR] Download failed: $_"
    Write-Host ""
    Write-Host "Please download manually from:"
    Write-Host "https://ffmpeg.org/download.html"
    exit 1
}

# Extract FFmpeg
Write-Host "[*] Extracting FFmpeg..."
try {
    Expand-Archive -Path $outputPath -DestinationPath $tempDir -Force
    Write-Host "[SUCCESS] Extraction complete"
    Write-Host ""
} catch {
    Write-Host "[ERROR] Extraction failed: $_"
    exit 1
}

# Find FFmpeg binary
Write-Host "[*] Finding FFmpeg executable..."
$ffmpegExe = Get-ChildItem -Path $tempDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1

if (-not $ffmpegExe) {
    Write-Host "[ERROR] FFmpeg executable not found"
    exit 1
}

$ffmpegBinPath = $ffmpegExe.DirectoryName
Write-Host "[SUCCESS] FFmpeg found at: $ffmpegBinPath"
Write-Host ""

# Create destination directory
$installDir = "C:\ffmpeg"
if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}

Write-Host "[*] Copying FFmpeg to: $installDir"
Copy-Item -Path "$ffmpegBinPath\*" -Destination $installDir -Force -Recurse

# Add to PATH
Write-Host "[*] Adding FFmpeg to system PATH..."
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")

if ($currentPath -notlike "*ffmpeg*") {
    $newPath = if ($currentPath) { "$currentPath;$installDir" } else { $installDir }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "[SUCCESS] Added FFmpeg to PATH"
} else {
    Write-Host "[INFO] FFmpeg already in PATH"
}

# Refresh environment variable for current session
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

Write-Host ""
Write-Host "[*] Cleaning up temporary files..."
Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host ""
Write-Host "============================================"
Write-Host "    Installation Complete!"
Write-Host "============================================"
Write-Host ""

# Verify installation
try {
    $ffmpegTest = & ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Host "[SUCCESS] FFmpeg verification passed!"
    Write-Host $ffmpegTest
    Write-Host ""
} catch {
    Write-Host "[WARNING] FFmpeg not found in current session"
    Write-Host "[INFO] Please close and reopen your terminal/VS Code"
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Close all terminals and VS Code completely"
Write-Host "2. Reopen VS Code/Terminal"
Write-Host "3. Restart the Flask app"
Write-Host "4. Try generating audio again"
Write-Host ""

Write-Host "Installation directory: $installDir"
Write-Host ""
