"""Anvil Runner - Serial output colorization and pipe listener."""

from __future__ import annotations

import asyncio
import re
from typing import Optional, Callable

from core.logger import Logger, get_logger


class SerialColorizer:
    """Colorize serial output and radical clean of UEFI/ANSI garbage."""
    
    # Remove qualquer código de controle ANSI [ ... ]
    ANSI_CLEANER = re.compile(r"\x1b\[[0-9;?]*[A-Za-z=]")
    
    TAG_PATTERNS = [
        (r"\[OK\]", "[green][OK][/green]"),
        (r"\[FAIL\]", "[bold red][FAIL][/bold red]"),
        (r"\[ERROR\]", "[bold red][ERROR][/bold red]"),
        (r"\[WARN\]", "[red][WARN][/red]"),
        (r"\[TRACE\]", "[magenta][TRACE][/magenta]"),
        (r"\[DEBUG\]", "[grey58][DEBUG][/grey58]"),
        (r"\[INFO\]", "[cyan][INFO][/cyan]"),
        (r"\[Supervisor\]", "[#ffa500][Supervisor][/#ffa500]"),
        (r"\[Compositor\]", "[blue][Compositor][/blue]"),
        (r"\[Shell\]", "[green][Shell][/green]"),
        (r"\[Input\]", "[magenta][Input][/magenta]"),
        (r"\[JUMP\]", "[magenta][JUMP][/magenta]"),
    ]
    
    @classmethod
    def colorize(cls, line: str) -> str:
        # 1. Limpeza radical: remove códigos de escape
        line = cls.ANSI_CLEANER.sub("", line)
        
        # 2. Mantém apenas caracteres ASCII visíveis padrão e espaços
        # Isso remove de vez os quadrados/lixo do UEFI
        line = "".join(ch for ch in line if 32 <= ord(ch) <= 126 or ch == '\n' or ch == '\r')
        
        if not line.strip():
            return ""

        # 3. Aplicar as cores do Anvil
        for pattern, replacement in cls.TAG_PATTERNS:
            line = re.sub(pattern, replacement, line)
        
        line = re.sub(r"(?<!\[)'([^'\]]+)'(?!\[)", r"[green]'\1'[/green]", line)
        line = re.sub(r"(?<!\[)\(([a-zA-Z0-9_ ]+)\)(?![\w\]])", r"[cyan](\1)[/cyan]", line)
        line = re.sub(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\(\)", r"[cyan]\1()[/cyan]", line)
        line = re.sub(r"\b(0x[0-9a-fA-F]+)\b", r"[yellow]\1[/yellow]", line)
        line = re.sub(r"(?<![a-zA-Z#\[])\b(\d+(?:\.\d+)?)\b(?![a-zA-Z])", r"[yellow]\1[/yellow]", line)
        
        return line


class PipeListener:
    """Listen for serial output via Windows Named Pipe asynchronously."""
    
    def __init__(
        self,
        pipe_path: str = r"\\.\pipe\VBoxCom1",
        log: Optional[Logger] = None,
        on_line: Optional[Callable[[str], None]] = None,
    ):
        self.pipe_path = pipe_path
        self.log = log or get_logger()
        self.on_line = on_line
        self._stop_event = asyncio.Event()
        self._buffer = ""
    
    async def start(self) -> None:
        asyncio.create_task(self._run_loop())

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await asyncio.get_event_loop().run_in_executor(None, self._read_pipe)
            except Exception:
                await asyncio.sleep(1)
    
    def _read_pipe(self) -> None:
        try:
            with open(self.pipe_path, "rb") as f:
                self.log.success("Status: CONECTADO")
                while not self._stop_event.is_set():
                    chunk = f.read(1024)
                    if not chunk: break
                    text = chunk.decode("utf-8", errors="replace")
                    self._buffer += text
                    if "\n" in self._buffer:
                        lines = self._buffer.split("\n")
                        self._buffer = lines.pop()
                        for line in lines:
                            out = SerialColorizer.colorize(line)
                            if out and self.on_line: self.on_line(out)
        except Exception:
            pass
    
    def stop(self) -> None:
        self._stop_event.set()
