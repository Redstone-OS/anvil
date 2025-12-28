"""
Anvil Analysis - Detector de exceções de CPU
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class CpuException:
    """Exceção de CPU detectada."""
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
    rflags: Optional[str] = None
    raw_line: str = ""
    
    def __str__(self) -> str:
        parts = [f"{self.name} ({self.code})"]
        if self.rip:
            parts.append(f"RIP={self.rip}")
        if self.cr2:
            parts.append(f"CR2={self.cr2}")
        return " ".join(parts)


@dataclass
class ExceptionContext:
    """Contexto completo de uma exceção."""
    exception: CpuException
    registers: dict[str, str] = field(default_factory=dict)
    stack_dump: list[str] = field(default_factory=list)
    code_around_rip: list[str] = field(default_factory=list)
    recent_interrupts: list[str] = field(default_factory=list)


class ExceptionDetector:
    """Detector de exceções de CPU em logs QEMU."""
    
    # Mapeamento de vetores para nomes
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
        0x13: ("SIMD FP Exception", "#XM"),
        0x14: ("Virtualization", "#VE"),
    }
    
    # Regex patterns
    EXCEPTION_PATTERN = re.compile(
        r"check_exception.*v=([0-9a-fA-F]+)"
        r"|.*v=([0-9a-fA-F]{2})\s+e=([0-9a-fA-F]+)",
        re.IGNORECASE,
    )
    
    RIP_PATTERN = re.compile(r"RIP=([0-9a-fA-Fx]+)", re.IGNORECASE)
    CR2_PATTERN = re.compile(r"CR2=([0-9a-fA-Fx]+)", re.IGNORECASE)
    RSP_PATTERN = re.compile(r"RSP=([0-9a-fA-Fx]+)", re.IGNORECASE)
    CS_PATTERN = re.compile(r"CS\s*=\s*([0-9a-fA-Fx]+)", re.IGNORECASE)
    SS_PATTERN = re.compile(r"SS\s*=\s*([0-9a-fA-Fx]+)", re.IGNORECASE)
    
    def __init__(self):
        self._last_rip: Optional[str] = None
        self._last_registers: dict[str, str] = {}
        self._recent_interrupts: list[str] = []
    
    def process_line(self, line: str) -> None:
        """Processa linha para extrair informações de contexto."""
        # Atualizar RIP
        rip_match = self.RIP_PATTERN.search(line)
        if rip_match:
            self._last_rip = rip_match.group(1)
        
        # Atualizar registradores
        for pattern, name in [
            (self.CR2_PATTERN, "CR2"),
            (self.RSP_PATTERN, "RSP"),
            (self.CS_PATTERN, "CS"),
            (self.SS_PATTERN, "SS"),
        ]:
            match = pattern.search(line)
            if match:
                self._last_registers[name] = match.group(1)
        
        # Rastrear interrupções recentes
        if "Servicing hardware INT=" in line:
            self._recent_interrupts.append(line)
            if len(self._recent_interrupts) > 10:
                self._recent_interrupts.pop(0)
    
    def detect(self, line: str) -> Optional[CpuException]:
        """
        Detecta exceção de CPU na linha.
        
        Returns:
            CpuException se detectado, None caso contrário
        """
        # Processar linha para contexto
        self.process_line(line)
        
        # Verificar padrão de exceção
        match = self.EXCEPTION_PATTERN.search(line)
        if not match:
            # Fallback: verificar padrões simples
            for vec_hex, (name, code) in self.EXCEPTION_MAP.items():
                pattern = f"v={vec_hex:02x}"
                if pattern in line.lower():
                    return self._create_exception(vec_hex, line)
            return None
        
        # Extrair vetor
        vector_str = match.group(1) or match.group(2)
        if not vector_str:
            return None
        
        try:
            vector = int(vector_str, 16)
        except ValueError:
            return None
        
        return self._create_exception(vector, line)
    
    def _create_exception(self, vector: int, line: str) -> CpuException:
        """Cria objeto CpuException."""
        name, code = self.EXCEPTION_MAP.get(vector, (f"Exception {vector}", f"#0x{vector:02X}"))
        
        # Extrair error code se presente
        error_code = None
        ec_match = re.search(r"e=([0-9a-fA-F]+)", line)
        if ec_match:
            try:
                error_code = int(ec_match.group(1), 16)
            except ValueError:
                pass
        
        return CpuException(
            timestamp=datetime.now(),
            vector=vector,
            name=name,
            code=code,
            error_code=error_code,
            rip=self._last_rip,
            cr2=self._last_registers.get("CR2"),
            rsp=self._last_registers.get("RSP"),
            cs=self._last_registers.get("CS"),
            ss=self._last_registers.get("SS"),
            raw_line=line,
        )
    
    def extract_context(self, lines: list[str], exception: CpuException) -> ExceptionContext:
        """Extrai contexto completo para a exceção."""
        registers = dict(self._last_registers)
        
        # Procurar dump de registradores nas linhas
        for line in lines:
            for reg in ["RAX", "RBX", "RCX", "RDX", "RSI", "RDI", "RBP", "R8", "R9", 
                       "R10", "R11", "R12", "R13", "R14", "R15"]:
                pattern = re.compile(rf"{reg}=([0-9a-fA-Fx]+)", re.IGNORECASE)
                match = pattern.search(line)
                if match:
                    registers[reg] = match.group(1)
        
        return ExceptionContext(
            exception=exception,
            registers=registers,
            recent_interrupts=list(self._recent_interrupts),
        )
