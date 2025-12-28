"""
Anvil Analysis - Parser de logs QEMU
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterator
from collections import deque

from anvil.analysis.exception_detector import ExceptionDetector, CpuException


@dataclass
class LogEvent:
    """Evento parseado do log."""
    timestamp: datetime
    line_number: int
    raw_line: str
    event_type: str = "unknown"
    details: dict = field(default_factory=dict)


class LogParser:
    """Parser de logs QEMU com análise estruturada."""
    
    # Patterns para eventos
    INTERRUPT_PATTERN = re.compile(r"Servicing hardware INT=0x([0-9a-fA-F]+)")
    EXCEPTION_PATTERN = re.compile(r"check_exception|v=[0-9a-fA-F]{2}")
    MMU_PATTERN = re.compile(r"MMU|page fault|TLB", re.IGNORECASE)
    IO_PATTERN = re.compile(r"(in|out)[bwl] .* = ", re.IGNORECASE)
    
    def __init__(self, context_size: int = 100):
        self.context_size = context_size
        self.exception_detector = ExceptionDetector()
        self._context_buffer: deque[LogEvent] = deque(maxlen=context_size)
        self._irq_counts: dict[int, int] = {}
        self._line_count = 0
    
    def parse_line(self, line: str) -> LogEvent:
        """Parseia uma linha do log."""
        self._line_count += 1
        stripped = line.strip()
        
        event = LogEvent(
            timestamp=datetime.now(),
            line_number=self._line_count,
            raw_line=stripped,
        )
        
        # Classificar evento
        if self.EXCEPTION_PATTERN.search(stripped):
            event.event_type = "exception"
            # Detectar exceção
            exc = self.exception_detector.detect(stripped)
            if exc:
                event.details["exception"] = exc
        
        elif self.INTERRUPT_PATTERN.search(stripped):
            event.event_type = "interrupt"
            match = self.INTERRUPT_PATTERN.search(stripped)
            if match:
                irq = int(match.group(1), 16)
                event.details["irq"] = irq
                self._irq_counts[irq] = self._irq_counts.get(irq, 0) + 1
        
        elif self.MMU_PATTERN.search(stripped):
            event.event_type = "mmu"
        
        elif self.IO_PATTERN.search(stripped):
            event.event_type = "io"
        
        elif stripped.startswith("RIP=") or "RAX=" in stripped:
            event.event_type = "registers"
        
        # Adicionar ao buffer de contexto
        self._context_buffer.append(event)
        
        # Processar para detector de exceções
        self.exception_detector.process_line(stripped)
        
        return event
    
    def parse_file(self, path: Path) -> Iterator[LogEvent]:
        """Parseia arquivo de log completo."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield self.parse_line(line)
    
    def get_context(self, lines: int = 50) -> list[LogEvent]:
        """Retorna últimos N eventos."""
        return list(self._context_buffer)[-lines:]
    
    def get_exceptions(self) -> list[CpuException]:
        """Retorna todas as exceções detectadas."""
        exceptions = []
        for event in self._context_buffer:
            if event.event_type == "exception" and "exception" in event.details:
                exceptions.append(event.details["exception"])
        return exceptions
    
    @property
    def irq_counts(self) -> dict[int, int]:
        """Retorna contagem de IRQs."""
        return dict(self._irq_counts)
    
    @property
    def total_lines(self) -> int:
        """Total de linhas processadas."""
        return self._line_count
    
    def analyze_summary(self) -> dict:
        """Gera resumo da análise."""
        events_by_type = {}
        for event in self._context_buffer:
            events_by_type[event.event_type] = events_by_type.get(event.event_type, 0) + 1
        
        return {
            "total_lines": self._line_count,
            "events_by_type": events_by_type,
            "irq_counts": self._irq_counts,
            "exceptions_count": events_by_type.get("exception", 0),
        }
