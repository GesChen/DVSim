@echo off
set "DIR=./output"

del /q "%DIR%\*" 2>nul
for /d %%D in ("%DIR%\*") do rd /s /q "%%D"