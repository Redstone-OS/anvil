"""Anvil Runner - Captura de Streams.

Gerencia a captura assíncrona de output do QEMU (serial e logs).
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

class StreamSource(Enum):
    """Fonte do log."""
    SERIAL = "serial"
    CPU_LOG = "cpu_log"

@dataclass
class LogEntry:
    timestamp: datetime
    source: StreamSource
    line: str
    line_number: int = 0

@dataclass
class StreamCapture:
    """
    Captura linhas de streams diferentes (stdout, arquivo).
    Armazena histórico recente para análise de crash.
    """
    serial_buffer: deque = field(default_factory=lambda: deque(maxlen=5000))
    cpu_buffer: deque = field(default_factory=lambda: deque(maxlen=5000))
    timeline: list = field(default_factory=list)
    _running: bool = False
    _callbacks: list = field(default_factory=list)
    
    def add_callback(self, callback):
        """Registra callback chamado para cada nova linha."""
        self._callbacks.append(callback)
    
    def _emit(self, entry):
        self.timeline.append(entry)
        for cb in self._callbacks:
            try: cb(entry)
            except: pass
            
    async def capture_serial(self, stream: asyncio.StreamReader):
        """Lê stdout do processo QEMU."""
        self._running = True
        count = 0
        while self._running:
            try:
                line = await asyncio.wait_for(stream.readline(), timeout=0.1)
                if not line: break
                count += 1
                entry = LogEntry(datetime.now(), StreamSource.SERIAL, line.decode("utf-8", "replace").rstrip(), count)
                self.serial_buffer.append(entry)
                self._emit(entry)
            except asyncio.TimeoutError: continue
            except: break
            
    async def capture_cpu_log(self, log_path: Path):
        """Monitora arquivo de log (-D do QEMU) estilo tail -f."""
        self._running = True
        # Espera arquivo ser criado
        while self._running and not log_path.exists(): await asyncio.sleep(0.1)
        if not self._running: return
        
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2) # Vai pro final
            count = 0
            while self._running:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.05)
                    continue
                stripped = line.rstrip()
                if not stripped: continue
                
                count += 1
                entry = LogEntry(datetime.now(), StreamSource.CPU_LOG, stripped, count)
                self.cpu_buffer.append(entry)
                self._emit(entry)
                
    def stop(self): self._running = False
    
    def get_context(self, lines=50): return list(self.timeline[-lines:])
    def get_serial(self, lines=50): return list(self.serial_buffer)[-lines:]
    def get_cpu(self, lines=50): return list(self.cpu_buffer)[-lines:]
    @property
    def total_lines(self): return len(self.timeline)
