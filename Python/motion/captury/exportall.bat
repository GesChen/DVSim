@echo off
setlocal

cd /d "%~dp0"

if not exist "input" (
    echo Input directory not found: %~dp0input
    exit /b 1
)

if not exist "output" mkdir "output"

for %%F in ("input\*.blend") do (
    if not exist "output\%%~nF.fbx" (
        echo Exporting %%~nxF...
        py "export.py" "%%~fF"

        if errorlevel 1 (
            echo Export failed: %%~nxF
            exit /b 1
        )
    )
)

endlocal