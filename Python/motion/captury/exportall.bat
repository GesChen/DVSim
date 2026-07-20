@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "INPUT_DIR=%SCRIPT_DIR%input"
set "OUTPUT_DIR=%SCRIPT_DIR%output"
set "PY_SCRIPT=%SCRIPT_DIR%export_armature.py"

if not exist "%INPUT_DIR%\" (
    echo Input directory not found: "%INPUT_DIR%"
    exit /b 1
)

if not exist "%OUTPUT_DIR%\" mkdir "%OUTPUT_DIR%"

for /D %%D in ("%INPUT_DIR%\*") do (
    if not exist "%OUTPUT_DIR%\%%~nxD.fbx" (
        echo Processing %%~nxD
        py "%PY_SCRIPT%" "%%~nxD"

        if errorlevel 1 (
            echo Failed: %%~nxD
            exit /b 1
        )
    )
)

exit /b 0