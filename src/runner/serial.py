"""Anvil Runner - Serial output colorization and pipe listener."""

from __future__ import annotations

import asyncio
import re
from typing import Optional, Callable

from core.logger import Logger, get_logger


class SerialColorizer:
    """
    Colorize serial output with Rich markup.
    
    Recognizes common logging tags and applies colors.
    """
    
    # Tag patterns and their Rich styles
    PATTERNS = [
        (r"\[OK\]", "[green][OK][/green]"),
        (r"\[FAIL\]", "[red bold][FAIL][/red bold]"),
        (r"\[JUMP\]", "[magenta][JUMP][/magenta]"),
        (r"\[TRACE\]", "[dim][TRACE][/dim]"),
        (r"\[DEBUG\]", "[dim cyan][DEBUG][/dim cyan]"),
        (r"\[INFO\]", "[cyan][INFO][/cyan]"),
        (r"\[WARN\]", "[yellow][WARN][/yellow]"),
        (r"\[ERROR\]", "[red][ERROR][/red]"),
        (r"\[Supervisor\]", "[#ffa500][Supervisor][/#ffa500]"),
        (r"\[Compositor\]", "[blue][Compositor][/blue]"),
        (r"\[Shell\]", "[green][Shell][/green]"),
        (r"\[Input\]", "[magenta][Input][/magenta]"),
    ]
    
    # ANSI escape sequence remover
    ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
    
    @classmethod
    def colorize(cls, line: str) -> str:
        """Apply Rich color markup to a serial line."""
        # Remove existing ANSI codes
        line = cls.ANSI_ESCAPE.sub("", line)
        
        # Apply our colors
        for pattern, replacement in cls.PATTERNS:
            line = re.sub(pattern, replacement, line)
        
        return line


class PipeListener:
    """
    Listen for serial output via Windows Named Pipe.
    
    Used with VirtualBox COM port redirection:
    - Create a Named Pipe in VirtualBox settings
    - Connect to it with this listener
    """
    
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
                await asyncio.get_event_loop().run_in_executor(
                    None, self._read_pipe
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._stop_event.is_set():
                    self.log.error(f"Pipe error: {e}")
                    await asyncio.sleep(2)
    
    def _read_pipe(self) -> None:
        """Blocking pipe read (runs in executor)."""
        try:
            with open(self.pipe_path, "rb") as f:
                self.log.success(f"Connected to pipe: {self.pipe_path}")
                
                while not self._stop_event.is_set():
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    
                    text = chunk.decode("utf-8", errors="replace")
                    self._buffer += text
                    
                    if "\n" in self._buffer:
                        lines = self._buffer.split("\n")
                        self._buffer = lines.pop()  # Keep incomplete line
                        
                        for line in lines:
                            colored = SerialColorizer.colorize(line)
                            
                            if self.on_line:
                                self.on_line(colored)
                            else:
                                self.log.raw(colored)
        
        except FileNotFoundError:
            # Pipe doesn't exist yet
            pass
        except Exception as e:
            if not self._stop_event.is_set():
                raise e
    
    def stop(self) -> None:
        """Stop listening."""
        self._stop_event.set()

