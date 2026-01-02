@echo off
cd /d "%~dp0"
title Anvil 0.0.5 - RedstoneOS

REM Adicionar src ao PYTHONPATH
set PYTHONPATH=%~dp0src

if "%1"=="" (
    REM Executar TUI
    python -c "import sys; sys.path.insert(0, r'%~dp0src'); from tui import run_tui; run_tui()"
) else (
    REM Executar CLI com argumentos
    python -m cli %*
)
