@echo off
cd /d "%~dp0"
title Anvil 4.0 - RedstoneOS

REM Adicionar src ao PYTHONPATH
set PYTHONPATH=%~dp0src

REM Executar TUI
python -c "import sys; sys.path.insert(0, r'%~dp0src'); from tui import run_tui; run_tui()"

pause
