@echo off
REM FFmpeg Automatic Installer for Windows
REM This script downloads and installs FFmpeg

echo.
echo ============================================
echo    FFmpeg Installation Script
echo ============================================
echo.

setlocal enabledelayedexpansion

REM Check if FFmpeg is already installed
ffmpeg -version >nul 2>&1
if %errorlevel% equ 0 (
    echo [SUCCESS] FFmpeg is already installed!
    ffmpeg -version
    pause
    exit /b 0
)

echo [*] FFmpeg not found. Installing...
echo.

REM Create temp directory
set "TEMP_DIR=%TEMP%\ffmpeg_install"
if not exist "!TEMP_DIR!" mkdir "!TEMP_DIR!"

echo [*] Downloading FFmpeg (this may take a minute)...
echo.

REM Download FFmpeg using PowerShell
powershell -Command "^
    $ProgressPreference = 'SilentlyContinue'; ^
    $url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'; ^
    $output = '%TEMP_DIR%\ffmpeg.zip'; ^
    try { ^
        Write-Host '[*] Downloading from GitHub...'; ^
        Invoke-WebRequest -Uri $url -OutFile $output -UseBasicParsing; ^
        Write-Host '[SUCCESS] Download complete'; ^
    } catch { ^
        Write-Host '[ERROR] Download failed'; ^
        exit 1; ^
    } ^
"

if %errorlevel% neq 0 (
    echo [ERROR] Download failed
    pause
    exit /b 1
)

echo.
echo [*] Extracting FFmpeg...
echo.

REM Extract FFmpeg
powershell -Command "^
    try { ^
        Expand-Archive -Path '%TEMP_DIR%\ffmpeg.zip' -DestinationPath '%TEMP_DIR%' -Force; ^
        Write-Host '[SUCCESS] Extraction complete'; ^
    } catch { ^
        Write-Host '[ERROR] Extraction failed'; ^
        exit 1; ^
    } ^
"

if %errorlevel% neq 0 (
    echo [ERROR] Extraction failed
    pause
    exit /b 1
)

echo.
echo [*] Finding FFmpeg executable...
echo.

REM Find FFmpeg binary
for /r "!TEMP_DIR!" %%F in (ffmpeg.exe) do (
    set "FFMPEG_PATH=%%~dpF"
    goto :found
)

:found
if not defined FFMPEG_PATH (
    echo [ERROR] FFmpeg executable not found
    pause
    exit /b 1
)

echo [*] FFmpeg found at: !FFMPEG_PATH!
echo.

REM Create destination directory
set "INSTALL_DIR=C:\ffmpeg"
if not exist "!INSTALL_DIR!" mkdir "!INSTALL_DIR!"

echo [*] Copying FFmpeg to: !INSTALL_DIR!
xcopy "!FFMPEG_PATH!*" "!INSTALL_DIR!" /Y /Q

echo.
echo [*] Adding FFmpeg to system PATH...
echo.

REM Add to PATH using PowerShell
powershell -Command "^
    $ffmpegPath = 'C:\ffmpeg'; ^
    $currentPath = [Environment]::GetEnvironmentVariable('Path', 'User'); ^
    if ($currentPath -notlike '*ffmpeg*') { ^
        $newPath = $currentPath + ';' + $ffmpegPath; ^
        [Environment]::SetEnvironmentVariable('Path', $newPath, 'User'); ^
        Write-Host '[SUCCESS] Added FFmpeg to PATH'; ^
    } else { ^
        Write-Host '[INFO] FFmpeg already in PATH'; ^
    } ^
"

echo.
echo [*] Refreshing environment variables...
setx PATH "%PATH%;C:\ffmpeg" >nul 2>&1

echo.
echo [*] Cleaning up temporary files...
rmdir /s /q "!TEMP_DIR!" 2>nul

echo.
echo.
echo ============================================
echo    Installation Complete!
echo ============================================
echo.
echo [SUCCESS] FFmpeg has been installed!
echo.
echo Next steps:
echo 1. Close all terminals and VS Code
echo 2. Reopen VS Code/Terminal
echo 3. Restart your Flask app
echo 4. Try generating audio again
echo.

REM Verify installation
echo [*] Verifying installation...
ffmpeg -version >nul 2>&1
if %errorlevel% equ 0 (
    echo [SUCCESS] FFmpeg verification passed!
    echo.
) else (
    echo [WARNING] FFmpeg verification failed in this terminal
    echo [INFO] Please restart your terminal and try again
    echo.
)

pause
