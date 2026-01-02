"""Anvil Runner - Serial output colorization and pipe listener."""

from __future__ import annotations

import asyncio
import re
from typing import Optional, Callable

from core.logger import Logger, get_logger


class SerialColorizer:
    """
    Colorize serial output with Rich markup.
    
    Color scheme:
    - [TRACE]      -> Magenta (Rosa)
    - [DEBUG]      -> Grey (Cinza)
    - [INFO]       -> Blue (Azul)
    - [Supervisor] -> Orange (Laranja)
    - [WARN]       -> Red (Vermelho)
    - [OK]         -> Green (Verde)
    - [ERROR]      -> Bold Red
    - Funções ()   -> Cyan
    - 'Texto'      -> Green
    - (Word)       -> Cyan
    - Números      -> Yellow
    """
    
    ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
    
    # Priority patterns (tags)
    TAG_PATTERNS = [
        (r"\[OK\]", "[green][OK][/green]"),
        (r"\[FAIL\]", "[bold red][FAIL][/bold red]"),
        (r"\[ERROR\]", "[bold red][ERROR][/bold red]"),
        (r"\[WARN\]", "[red][WARN][/red]"),
        (r"\[TRACE\]", "[magenta][TRACE][/magenta]"),
        (r"\[DEBUG\]", "[grey58][DEBUG][/grey58]"),
        (r"\[INFO\]", "[blue][INFO][/blue]"),
        (r"\[Supervisor\]", "[#ffa500][Supervisor][/#ffa500]"),
        (r"\[Compositor\]", "[blue][Compositor][/blue]"),
        (r"\[Shell\]", "[green][Shell][/green]"),
        (r"\[Input\]", "[magenta][Input][/magenta]"),
        (r"\[JUMP\]", "[magenta][JUMP][/magenta]"),
    ]
    
    @classmethod
    def colorize(cls, line: str) -> str:
        """Apply Rich color markup to a serial line."""
        # 1. Strip ANSI
        line = cls.ANSI_ESCAPE.sub("", line)
        
        # 2. Apply level tags
        for pattern, replacement in cls.TAG_PATTERNS:
            line = re.sub(pattern, replacement, line)
        
        # 3. Quoted text 'like this' -> Green (Avoids breaking already colored bits)
        # Using a regex that tries to avoid crossing colored tags
        line = re.sub(r"(?<!\[)'([^'\]]+)'(?!\[)", r"[green]'\1'[/green]", line)
        
        # 4. (Word) patterns like (Heap) or (MM) -> Cyan
        line = re.sub(r"(?<!\[)\(([a-zA-Z0-9_ ]+)\)(?!\((?:/?[a-z]+|#[0-9a-f]+)\])", r"[cyan](\1)[/cyan]", line)
        
        # 5. Functions like read_file() -> Cyan (only the name and parens)
        line = re.sub(r"\b([a-zA-Z0-9_]+)\(\)", r"[cyan]\1()[/cyan]", line)
        
        # 6. Numbers (Hex and Dec) -> Yellow
        # Hex
        line = re.sub(r"\b(0x[0-9a-fA-F]+)\b", r"[yellow]\1[/yellow]", line)
        # Dec (only if not inside a tag or word)
        line = re.sub(r"(?<![a-zA-Z0-9_])(\d+(?:\.\d+)?)(?![a-zA-Z0-9_])", r"[yellow]\1[/yellow]", line)
        
        return line


class PipeListener:
    """Listen for serial output via Windows Named Pipe."""
    
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
        """Start listening on the pipe."""
        self.log.header(f"Serial Pipe: {self.pipe_path}")
        while not self._stop_event.is_set():
            try:
                await asyncio.get_event_loop().run_in_executor(None, self._read_pipe)
            except asyncio.CancelledError: break
            except Exception as e:
                if not self._stop_event.is_set():
                    self.log.error(f"Pipe error: {e}")
                    await asyncio.sleep(2)
    
    def _read_pipe(self) -> None:
        try:
            with open(self.pipe_path, "rb") as f:
                self.log.success(f"Connected to pipe: {self.pipe_path}")
                while not self._stop_event.is_set():
                    chunk = f.read(1024)
                    if not chunk: break
                    text = chunk.decode("utf-8", errors="replace")
                    self._buffer += text
                    if "\n" in self._buffer:
                        lines = self._buffer.split("\n")
                        self._buffer = lines.pop()
                        for line in lines:
                            colored = SerialColorizer.colorize(line)
                            if self.on_line: self.on_line(colored)
                            else: self.log.raw(colored)
        except FileNotFoundError: pass
        except Exception as e:
            if not self._stop_event.is_set(): raise e
    
    def stop(self) -> None:
        self._stop_event.set()
