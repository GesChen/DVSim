@echo off
setlocal EnableExtensions
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher "py" was not found.
    pause
    exit /b 1
)

py -c "import PIL" >nul 2>nul
if errorlevel 1 (
    echo Installing Pillow...
    py -m pip install Pillow
    if errorlevel 1 (
        echo Failed to install Pillow.
        pause
        exit /b 1
    )
)

echo Drag each texture into this window and press Enter.
echo Press Enter without a path to skip any texture.
echo.

set /p "COLOR=Base color / albedo: "
set /p "OPACITY=Opacity / alpha: "
set /p "METALLIC=Metallic: "
set /p "AO=Ambient occlusion: "
set /p "ROUGHNESS=Roughness: "
if not defined ROUGHNESS set /p "SMOOTHNESS=Smoothness instead: "
set /p "NORMAL=Normal map: "
set /p "HEIGHT=Height / displacement: "
set /p "OUTPUT=Output folder, or Enter for input folder: "
set /p "NAME=Output base name, or Enter for automatic: "

py "%~dp0unity_texture_packer.py" ^
  --color "%COLOR%" ^
  --opacity "%OPACITY%" ^
  --metallic "%METALLIC%" ^
  --ao "%AO%" ^
  --roughness "%ROUGHNESS%" ^
  --smoothness "%SMOOTHNESS%" ^
  --normal "%NORMAL%" ^
  --height "%HEIGHT%" ^
  --output-dir "%OUTPUT%" ^
  --name "%NAME%"

if errorlevel 1 echo.
pause
