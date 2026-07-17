@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "TARGET=E:\DVSim\Python\interior\3D-Front"
set "BASE=https://huggingface.co/datasets/huanngzh/3D-Front/resolve/main"

if not exist "%TARGET%" mkdir "%TARGET%"
cd /d "%TARGET%" || exit /b 1

where aria2c >nul 2>&1 || (
echo aria2c.exe not found in PATH.
exit /b 1
)

echo Downloading scene archive parts...

for %%P in (aa ab ac ad ae af ag ah ai aj ak al am) do (
aria2c ^
--continue=true ^
--always-resume=true ^
--max-connection-per-server=8 ^
--split=8 ^
--min-split-size=64M ^
--max-tries=0 ^
--retry-wait=10 ^
--file-allocation=none ^
--summary-interval=0 ^
--show-console-readout=true ^
--console-log-level=error ^
--download-result=hide ^
--out="3D-FRONT-SCENE.part%%P" ^
"%BASE%/3D-FRONT-SCENE.part%%P?download=true"


if errorlevel 1 (
    echo Download failed: 3D-FRONT-SCENE.part%%P
    exit /b 1
)


)

echo Merging parts...

copy /b ^
3D-FRONT-SCENE.partaa+^
3D-FRONT-SCENE.partab+^
3D-FRONT-SCENE.partac+^
3D-FRONT-SCENE.partad+^
3D-FRONT-SCENE.partae+^
3D-FRONT-SCENE.partaf+^
3D-FRONT-SCENE.partag+^
3D-FRONT-SCENE.partah+^
3D-FRONT-SCENE.partai+^
3D-FRONT-SCENE.partaj+^
3D-FRONT-SCENE.partak+^
3D-FRONT-SCENE.partal+^
3D-FRONT-SCENE.partam ^
3D-FRONT-SCENE.tar.gz

if errorlevel 1 (
echo Merge failed.
exit /b 1
)

echo Deleting merged parts...

for %%P in (aa ab ac ad ae af ag ah ai aj ak al am) do (
del /q "3D-FRONT-SCENE.part%%P"


if exist "3D-FRONT-SCENE.part%%P" (
    echo Failed to delete: 3D-FRONT-SCENE.part%%P
    exit /b 1
)


)

echo Extracting...

tar -xzf 3D-FRONT-SCENE.tar.gz

if errorlevel 1 (
echo Extraction failed.
exit /b 1
)

echo Done.
pause
