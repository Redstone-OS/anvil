@echo off
cd /d "%~dp0"
title Anvil 0.0.6 - RedstoneOS

REM Adiciona src ao PYTHONPATH para que os módulos sejam encontrados
set PYTHONPATH=%~dp0src

if "%1"=="menu" (
    REM Forçar TUI mesmo com argumento
    python -c "from tui import run_tui; run_tui()"
) else if "%1"=="" (
    REM Executar TUI por padrão
    python -c "from tui import run_tui; run_tui()"
) else (
    REM Executar CLI com argumentos
    python -m cli %*
)
