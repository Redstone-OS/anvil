@echo off
cd /d "%~dp0"
title Anvil - RedstoneOS Builder
set PYTHONPATH=%~dp0src

python src/main.py
pause
