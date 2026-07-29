@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem ============================================================
rem Configuration
rem ============================================================

set "SCALE=10"
set "FLIP_X=false"
set "FLIP_Y=false"
set "TILEABLE=false"

rem Locate GEGL bundled with GIMP.
set "GEGL="

for %%P in (
    "%ProgramFiles%\GIMP 3\bin\gegl.exe"
    "%ProgramFiles%\GIMP 2\bin\gegl.exe"
    "%ProgramFiles%\GIMP 2\lib\gegl-0.4\gegl.exe"
    "%LocalAppData%\Programs\GIMP 3\bin\gegl.exe"
) do (
    if exist "%%~P" set "GEGL=%%~P"
)

rem Fall back to PATH.
if not defined GEGL (
    where gegl.exe >nul 2>&1
    if not errorlevel 1 set "GEGL=gegl.exe"
)

if not defined GEGL (
    echo ERROR: Could not find gegl.exe.
    echo Edit this script and set GEGL to GIMP's gegl.exe location.
    pause
    exit /b 1
)

rem Folder may be passed as an argument or dragged onto this BAT.
if "%~1"=="" (
    set "INPUT_DIR=%CD%"
) else (
    set "INPUT_DIR=%~f1"
)

if not exist "%INPUT_DIR%\" (
    echo ERROR: Folder does not exist:
    echo "%INPUT_DIR%"
    pause
    exit /b 1
)

echo Input: "%INPUT_DIR%"
echo GEGL:  "%GEGL%"
echo Scale: %SCALE%
echo.

for %%E in (png jpg jpeg bmp tif tiff webp) do (
    for %%F in ("%INPUT_DIR%\*.%%E") do (
        if exist "%%~fF" call :PROCESS "%%~fF"
    )
)

echo.
echo Finished.
pause
exit /b 0


:PROCESS
set "INPUT=%~1"
set "NAME=%~n1"
set "OUTPUT=%~dpn1_normal.png"

rem Do not process previously generated normal maps.
echo(%NAME%| findstr /I /R "_normal$" >nul
if not errorlevel 1 (
    echo Skipping existing normal: "%~nx1"
    exit /b
)

echo Generating: "%~nx1"

"%GEGL%" "%INPUT%" -o "%OUTPUT%" -- ^
    gegl:normal-map ^
    scale=%SCALE% ^
    flip-x=%FLIP_X% ^
    flip-y=%FLIP_Y% ^
    tileable=%TILEABLE%

if errorlevel 1 (
    echo ERROR: Failed to process "%~nx1"
) else (
    echo Created: "%~nx1_normal.png"
)

exit /b