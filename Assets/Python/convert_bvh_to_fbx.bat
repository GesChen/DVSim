@echo off
setlocal

REM Drag one or more .bvh files onto this .bat file.
REM Edit BLENDER_EXE below if Blender is not installed in this location.

set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
set "SCRIPT_DIR=%~dp0"
set "PY_SCRIPT=%SCRIPT_DIR%convert_bvh_to_fbx.py"

if not exist "%BLENDER_EXE%" (
    echo Blender executable not found:
    echo "%BLENDER_EXE%"
    echo.
    echo Edit BLENDER_EXE inside this .bat file.
    pause
    exit /b 1
)

if "%~1"=="" (
    echo Drag one or more .bvh files onto this .bat file.
    pause
    exit /b 1
)

"%BLENDER_EXE%" --background --factory-startup --python "%PY_SCRIPT%" -- %*

if errorlevel 1 (
    echo.
    echo Conversion failed. Check messages above.
    pause
    exit /b 1
)

echo.
echo Conversion complete.
pause
