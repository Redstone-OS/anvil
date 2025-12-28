"""
Anvil Runner - Captura dual de streams assíncronos
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, AsyncIterator, Callable

from core.paths import PathResolver


class StreamSource(Enum):
    """Fonte do stream."""
    SERIAL = "serial"
    CPU_LOG = "cpu_log"


@dataclass
class LogEntry:
    """Entrada de log com timestamp e fonte."""
    timestamp: datetime
    source: StreamSource
    line: str
    line_number: int = 0
    
    def __str__(self) -> str:
        ts = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        return f"[{ts}] [{self.source.value:7}] {self.line}"


@dataclass
class DualStreamCapture:
    """
    Captura assíncrona de múltiplos streams com buffer.
    
    Captura simultaneamente:
    - stdout do QEMU (serial output)
    - Arquivo de log CPU (tail -f style)
    """
    
    serial_buffer: deque[LogEntry] = field(default_factory=lambda: deque(maxlen=1000))
    cpu_log_buffer: deque[LogEntry] = field(default_factory=lambda: deque(maxlen=1000))
    merged_timeline: list[LogEntry] = field(default_factory=list)
    
    _serial_line_count: int = 0
    _cpu_log_line_count: int = 0
    _running: bool = False
    _callbacks: list[Callable[[LogEntry], None]] = field(default_factory=list)
    
    def add_callback(self, callback: Callable[[LogEntry], None]) -> None:
        """Adiciona callback para novas entradas."""
        self._callbacks.append(callback)
    
    def _emit(self, entry: LogEntry) -> None:
        """Emite entrada para callbacks."""
        self.merged_timeline.append(entry)
        for callback in self._callbacks:
            callback(entry)
    
    async def capture_serial(self, stream: asyncio.StreamReader) -> None:
        """Captura stream serial (stdout do QEMU)."""
        self._running = True
        
        while self._running:
            try:
                line = await asyncio.wait_for(
                    stream.readline(),
                    timeout=0.1,
                )
                
                if not line:
                    break
                
                self._serial_line_count += 1
                decoded = line.decode("utf-8", errors="replace").rstrip()
                
                entry = LogEntry(
                    timestamp=datetime.now(),
                    source=StreamSource.SERIAL,
                    line=decoded,
                    line_number=self._serial_line_count,
                )
                
                self.serial_buffer.append(entry)
                self._emit(entry)
                
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
    
    async def capture_cpu_log(self, log_path: Path) -> None:
        """
        Captura arquivo de log CPU (tail -f style).
        Monitora arquivo e emite novas linhas.
        """
        self._running = True
        
        # Esperar arquivo existir
        while self._running and not log_path.exists():
            await asyncio.sleep(0.1)
        
        if not self._running:
            return
        
        # Abrir e ir para o final
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            # Ir para final
            f.seek(0, 2)
            
            while self._running:
                line = f.readline()
                
                if not line:
                    await asyncio.sleep(0.05)
                    continue
                
                self._cpu_log_line_count += 1
                stripped = line.rstrip()
                
                if not stripped:
                    continue
                
                entry = LogEntry(
                    timestamp=datetime.now(),
                    source=StreamSource.CPU_LOG,
                    line=stripped,
                    line_number=self._cpu_log_line_count,
                )
                
                self.cpu_log_buffer.append(entry)
                self._emit(entry)
    
    def stop(self) -> None:
        """Para captura."""
        self._running = False
    
    def get_context(self, lines: int = 50) -> list[LogEntry]:
        """Retorna últimas N linhas do timeline mesclado."""
        return list(self.merged_timeline[-lines:])
    
    def get_serial_context(self, lines: int = 50) -> list[LogEntry]:
        """Retorna últimas N linhas do serial."""
        return list(self.serial_buffer)[-lines:]
    
    def get_cpu_log_context(self, lines: int = 50) -> list[LogEntry]:
        """Retorna últimas N linhas do CPU log."""
        return list(self.cpu_log_buffer)[-lines:]
    
    def get_stream_content(self, source: StreamSource) -> list[LogEntry]:
        """Retorna todo o conteúdo capturado de uma fonte específica."""
        if source == StreamSource.SERIAL:
            return list(self.serial_buffer)
        elif source == StreamSource.CPU_LOG:
            return list(self.cpu_log_buffer)
        return []
    
    def search(self, pattern: str) -> list[LogEntry]:
        """Busca padrão em todas as entradas."""
        import re
        regex = re.compile(pattern, re.IGNORECASE)
        return [e for e in self.merged_timeline if regex.search(e.line)]
    
    @property
    def total_lines(self) -> int:
        """Total de linhas capturadas."""
        return len(self.merged_timeline)
