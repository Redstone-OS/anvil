"""Anvil Analysis - Log file parsing."""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from analysis.detector import ExceptionDetector, CpuException


@dataclass
class LogEvent:
    """Parsed log event."""
    timestamp: datetime
    line_number: int
    raw_line: str
    event_type: str = "unknown"
    details: dict = field(default_factory=dict)


class LogParser:
    """
    Parser for QEMU debug logs.
    
    Categorizes lines into event types:
    - exception: CPU exceptions
    - interrupt: Hardware interrupts
    - mmu: Memory management events
    - io: Port I/O operations
    - registers: Register dumps
    """
    
    INTERRUPT_RE = re.compile(r"Servicing hardware INT=0x([0-9a-fA-F]+)")
    EXCEPTION_RE = re.compile(r"check_exception|v=[0-9a-fA-F]{2}")
    MMU_RE = re.compile(r"MMU|page fault|TLB", re.IGNORECASE)
    IO_RE = re.compile(r"(in|out)[bwl] .* = ", re.IGNORECASE)
    
    def __init__(self, context_size: int = 100):
        self.context_size = context_size
        self.detector = ExceptionDetector()
        self._context: deque[LogEvent] = deque(maxlen=context_size)
        self._irq_counts: dict[int, int] = {}
        self._line_count = 0
    
    def parse_line(self, line: str) -> LogEvent:
        """Parse a single log line."""
        self._line_count += 1
        stripped = line.strip()
        
        event = LogEvent(
            timestamp=datetime.now(),
            line_number=self._line_count,
            raw_line=stripped,
        )
        
        # Classify event
        if self.EXCEPTION_RE.search(stripped):
            event.event_type = "exception"
            exc = self.detector.detect(stripped)
            if exc:
                event.details["exception"] = exc
        
        elif self.INTERRUPT_RE.search(stripped):
            event.event_type = "interrupt"
            match = self.INTERRUPT_RE.search(stripped)
            if match:
                irq = int(match.group(1), 16)
                event.details["irq"] = irq
                self._irq_counts[irq] = self._irq_counts.get(irq, 0) + 1
        
        elif self.MMU_RE.search(stripped):
            event.event_type = "mmu"
        
        elif self.IO_RE.search(stripped):
            event.event_type = "io"
        
        elif stripped.startswith("RIP=") or "RAX=" in stripped:
            event.event_type = "registers"
        
        self._context.append(event)
        self.detector.process_line(stripped)
        
        return event
    
    def parse_file(self, path: Path) -> Iterator[LogEvent]:
        """Parse entire log file."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield self.parse_line(line)
    
    def get_context(self, lines: int = 50) -> list[LogEvent]:
        """Get last N events."""
        return list(self._context)[-lines:]
    
    def get_exceptions(self) -> list[CpuException]:
        """Get all detected exceptions."""
        exceptions = []
        for event in self._context:
            if event.event_type == "exception" and "exception" in event.details:
                exceptions.append(event.details["exception"])
        return exceptions
    
    @property
    def irq_counts(self) -> dict[int, int]:
        """IRQ occurrence counts."""
        return dict(self._irq_counts)
    
    @property
    def total_lines(self) -> int:
        """Total lines processed."""
        return self._line_count
    
    def summary(self) -> dict:
        """Generate analysis summary."""
        events_by_type: dict[str, int] = {}
        for event in self._context:
            events_by_type[event.event_type] = (
                events_by_type.get(event.event_type, 0) + 1
            )
        
        return {
            "total_lines": self._line_count,
            "events_by_type": events_by_type,
            "irq_counts": self._irq_counts,
            "exceptions_count": events_by_type.get("exception", 0),
        }

