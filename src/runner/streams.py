"""Anvil Runner - Async stream capture."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable


class StreamSource(Enum):
    """Source of a log stream."""
    SERIAL = "serial"
    CPU_LOG = "cpu_log"


@dataclass
class LogEntry:
    """Single log entry with metadata."""
    timestamp: datetime
    source: StreamSource
    line: str
    line_number: int = 0
    
    def __str__(self) -> str:
        ts = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        return f"[{ts}] [{self.source.value:7}] {self.line}"


@dataclass
class StreamCapture:
    """
    Async stream capture with callbacks.
    
    Captures:
    - QEMU stdout (serial output)
    - QEMU debug log file (CPU events)
    
    Provides real-time callbacks and buffered history.
    """
    
    serial_buffer: deque[LogEntry] = field(
        default_factory=lambda: deque(maxlen=5000)
    )
    cpu_buffer: deque[LogEntry] = field(
        default_factory=lambda: deque(maxlen=5000)
    )
    timeline: list[LogEntry] = field(default_factory=list)
    
    _serial_count: int = 0
    _cpu_count: int = 0
    _running: bool = False
    _callbacks: list[Callable[[LogEntry], None]] = field(default_factory=list)
    
    def add_callback(self, callback: Callable[[LogEntry], None]) -> None:
        """Add callback for new entries."""
        self._callbacks.append(callback)
    
    def _emit(self, entry: LogEntry) -> None:
        """Emit entry to all callbacks."""
        self.timeline.append(entry)
        for callback in self._callbacks:
            try:
                callback(entry)
            except Exception:
                pass
    
    async def capture_serial(self, stream: asyncio.StreamReader) -> None:
        """Capture serial output from QEMU stdout."""
        self._running = True
        
        while self._running:
            try:
                line = await asyncio.wait_for(
                    stream.readline(),
                    timeout=0.1,
                )
                
                if not line:
                    break
                
                self._serial_count += 1
                decoded = line.decode("utf-8", errors="replace").rstrip()
                
                entry = LogEntry(
                    timestamp=datetime.now(),
                    source=StreamSource.SERIAL,
                    line=decoded,
                    line_number=self._serial_count,
                )
                
                self.serial_buffer.append(entry)
                self._emit(entry)
            
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
    
    async def capture_cpu_log(self, log_path: Path) -> None:
        """Capture CPU log file (tail -f style)."""
        self._running = True
        
        # Wait for file to exist
        while self._running and not log_path.exists():
            await asyncio.sleep(0.1)
        
        if not self._running:
            return
        
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            # Seek to end
            f.seek(0, 2)
            
            while self._running:
                line = f.readline()
                
                if not line:
                    await asyncio.sleep(0.05)
                    continue
                
                stripped = line.rstrip()
                if not stripped:
                    continue
                
                self._cpu_count += 1
                
                entry = LogEntry(
                    timestamp=datetime.now(),
                    source=StreamSource.CPU_LOG,
                    line=stripped,
                    line_number=self._cpu_count,
                )
                
                self.cpu_buffer.append(entry)
                self._emit(entry)
    
    def stop(self) -> None:
        """Stop capture."""
        self._running = False
    
    def get_context(self, lines: int = 50) -> list[LogEntry]:
        """Get last N entries from merged timeline."""
        return list(self.timeline[-lines:])
    
    def get_serial(self, lines: int = 50) -> list[LogEntry]:
        """Get last N serial entries."""
        return list(self.serial_buffer)[-lines:]
    
    def get_cpu(self, lines: int = 50) -> list[LogEntry]:
        """Get last N CPU log entries."""
        return list(self.cpu_buffer)[-lines:]
    
    def search(self, pattern: str) -> list[LogEntry]:
        """Search all entries by regex pattern."""
        import re
        regex = re.compile(pattern, re.IGNORECASE)
        return [e for e in self.timeline if regex.search(e.line)]
    
    @property
    def total_lines(self) -> int:
        """Total captured lines."""
        return len(self.timeline)

