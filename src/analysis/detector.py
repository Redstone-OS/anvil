"""Anvil Analysis - CPU exception detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CpuException:
    """Detected CPU exception."""
    timestamp: datetime
    vector: int
    name: str
    code: str
    error_code: Optional[int] = None
    rip: Optional[str] = None
    cr2: Optional[str] = None
    rsp: Optional[str] = None
    cs: Optional[str] = None
    ss: Optional[str] = None
    raw_line: str = ""
    
    def __str__(self) -> str:
        parts = [f"{self.name} ({self.code})"]
        if self.rip:
            parts.append(f"RIP={self.rip}")
        if self.cr2:
            parts.append(f"CR2={self.cr2}")
        return " ".join(parts)


class ExceptionDetector:
    """
    Detect CPU exceptions from QEMU debug logs.
    
    Tracks register state between lines to provide
    complete context when an exception is detected.
    """
    
    # Vector -> (name, mnemonic)
    EXCEPTION_MAP = {
        0x00: ("Divide Error", "#DE"),
        0x01: ("Debug", "#DB"),
        0x02: ("NMI", "NMI"),
        0x03: ("Breakpoint", "#BP"),
        0x04: ("Overflow", "#OF"),
        0x05: ("Bound Range", "#BR"),
        0x06: ("Invalid Opcode", "#UD"),
        0x07: ("Device Not Available", "#NM"),
        0x08: ("Double Fault", "#DF"),
        0x0A: ("Invalid TSS", "#TS"),
        0x0B: ("Segment Not Present", "#NP"),
        0x0C: ("Stack Fault", "#SS"),
        0x0D: ("General Protection", "#GP"),
        0x0E: ("Page Fault", "#PF"),
        0x10: ("x87 FPU Error", "#MF"),
        0x11: ("Alignment Check", "#AC"),
        0x12: ("Machine Check", "#MC"),
        0x13: ("SIMD Exception", "#XM"),
        0x14: ("Virtualization", "#VE"),
    }
    
    # Regex patterns
    EXCEPTION_RE = re.compile(
        r"check_exception.*v=([0-9a-fA-F]+)"
        r"|.*v=([0-9a-fA-F]{2})\s+e=([0-9a-fA-F]+)",
        re.IGNORECASE,
    )
    RIP_RE = re.compile(r"RIP=([0-9a-fA-Fx]+)", re.IGNORECASE)
    CR2_RE = re.compile(r"CR2=([0-9a-fA-Fx]+)", re.IGNORECASE)
    RSP_RE = re.compile(r"RSP=([0-9a-fA-Fx]+)", re.IGNORECASE)
    
    def __init__(self):
        self._last_rip: Optional[str] = None
        self._last_regs: dict[str, str] = {}
    
    def process_line(self, line: str) -> None:
        """Track register state from a log line."""
        # Update RIP
        rip_match = self.RIP_RE.search(line)
        if rip_match:
            self._last_rip = rip_match.group(1)
        
        # Update other registers
        for pattern, name in [
            (self.CR2_RE, "CR2"),
            (self.RSP_RE, "RSP"),
        ]:
            match = pattern.search(line)
            if match:
                self._last_regs[name] = match.group(1)
    
    def detect(self, line: str) -> Optional[CpuException]:
        """
        Detect exception in a log line.
        
        Returns CpuException if found, None otherwise.
        """
        self.process_line(line)
        
        # Check for exception pattern
        match = self.EXCEPTION_RE.search(line)
        if match:
            vector_str = match.group(1) or match.group(2)
            if vector_str:
                try:
                    vector = int(vector_str, 16)
                    return self._create_exception(vector, line, match.group(3))
                except ValueError:
                    pass
        
        # Fallback: check for common patterns
        for vec, (name, code) in self.EXCEPTION_MAP.items():
            pattern = f"v={vec:02x}"
            if pattern in line.lower():
                return self._create_exception(vec, line)
        
        return None
    
    def _create_exception(
        self,
        vector: int,
        line: str,
        error_code_str: Optional[str] = None,
    ) -> CpuException:
        """Create exception object with current context."""
        name, code = self.EXCEPTION_MAP.get(
            vector,
            (f"Exception {vector}", f"#0x{vector:02X}"),
        )
        
        error_code = None
        if error_code_str:
            try:
                error_code = int(error_code_str, 16)
            except ValueError:
                pass
        
        return CpuException(
            timestamp=datetime.now(),
            vector=vector,
            name=name,
            code=code,
            error_code=error_code,
            rip=self._last_rip,
            cr2=self._last_regs.get("CR2"),
            rsp=self._last_regs.get("RSP"),
            raw_line=line,
        )

