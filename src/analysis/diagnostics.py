"""Anvil Analysis - Intelligent crash diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.config import Config
from core.paths import Paths
from core.logger import Logger, get_logger
from analysis.detector import CpuException
from analysis.inspector import BinaryInspector, Symbol, Disassembly
from analysis.patterns import Pattern, Severity, find_patterns
from runner.streams import LogEntry


@dataclass
class Diagnosis:
    """Complete crash diagnosis."""
    timestamp: datetime
    exception: CpuException
    
    # Analysis results
    symbol: Optional[Symbol] = None
    disassembly: Optional[Disassembly] = None
    matching_patterns: list[Pattern] = field(default_factory=list)
    
    # Conclusions
    probable_cause: str = ""
    suggestions: list[str] = field(default_factory=list)
    severity: Severity = Severity.CRITICAL
    
    # Context
    context_lines: list[LogEntry] = field(default_factory=list)
    register_analysis: list[str] = field(default_factory=list)


class DiagnosticEngine:
    """
    Intelligent crash diagnosis engine.
    
    Pipeline:
    1. Identify exception type
    2. Extract context (RIP, CR2, registers)
    3. Disassemble code at RIP
    4. Find symbol/function
    5. Match known error patterns
    6. Analyze register anomalies
    7. Generate diagnosis with suggestions
    """
    
    def __init__(
        self,
        paths: Paths,
        config: Config,
        log: Optional[Logger] = None,
    ):
        self.paths = paths
        self.config = config
        self.log = log or get_logger()
        self.inspector = BinaryInspector(paths, log)
    
    async def analyze(
        self,
        crash_info,  # CrashInfo from monitor
        profile: str = "release",
    ) -> Diagnosis:
        """
        Analyze crash and generate complete diagnosis.
        """
        # Create exception object
        exception = CpuException(
            timestamp=crash_info.timestamp,
            vector=self._code_to_vector(crash_info.exception_code),
            name=crash_info.exception_type,
            code=crash_info.exception_code,
            rip=crash_info.rip,
            cr2=crash_info.cr2,
            rsp=crash_info.rsp,
            raw_line="",
        )
        
        diagnosis = Diagnosis(
            timestamp=datetime.now(),
            exception=exception,
            context_lines=crash_info.context_lines,
        )
        
        # 1. Find matching patterns
        context_text = "\n".join(e.line for e in crash_info.context_lines)
        diagnosis.matching_patterns = find_patterns(context_text)
        
        # 2. Find symbol at RIP
        if exception.rip:
            try:
                rip_str = exception.rip.replace("RIP=", "").replace("0x", "")
                rip_addr = int(rip_str, 16)
                kernel = self.paths.kernel_binary(profile)
                
                if kernel.exists():
                    diagnosis.symbol = await self.inspector.find_symbol(
                        kernel, rip_addr
                    )
                    
                    # 3. Disassemble
                    diagnosis.disassembly = await self.inspector.disassemble_at(
                        kernel, rip_addr
                    )
            except ValueError:
                pass
        
        # 4. Analyze registers
        diagnosis.register_analysis = self._analyze_registers(
            crash_info.context_lines,
            exception.rip,
        )
        
        # 5. Determine probable cause
        diagnosis.probable_cause = self._determine_cause(diagnosis)
        diagnosis.suggestions = self._generate_suggestions(diagnosis)
        
        # 6. Determine severity
        if diagnosis.matching_patterns:
            diagnosis.severity = max(p.severity for p in diagnosis.matching_patterns)
        
        return diagnosis
    
    def _code_to_vector(self, code: str) -> int:
        """Convert exception code to vector number."""
        mapping = {
            "#DE": 0x00,
            "#UD": 0x06,
            "#DF": 0x08,
            "#GP": 0x0D,
            "#PF": 0x0E,
        }
        return mapping.get(code, 0)
    
    def _analyze_registers(
        self,
        context: list[LogEntry],
        rip: Optional[str],
    ) -> list[str]:
        """Analyze register values for anomalies."""
        import re
        
        findings = []
        regs: dict[str, int] = {}
        
        # Extract last register values from context
        for entry in reversed(context):
            matches = re.findall(
                r"([R|E][A-Z0-9]+)=([0-9a-fA-F]+)",
                entry.line,
            )
            for reg, val in matches:
                if reg not in regs:
                    try:
                        regs[reg] = int(val, 16)
                    except ValueError:
                        pass
            
            if "RIP" in regs and "RAX" in regs:
                break
        
        if not regs:
            return []
        
        # Check for NULL pointers
        for reg in ["RAX", "RBX", "RCX", "RDX", "RSI", "RDI", "RBP"]:
            if reg in regs and regs[reg] == 0:
                findings.append(f"{reg} is NULL - may cause crash if dereferenced")
        
        # Check for non-canonical addresses
        for reg, val in regs.items():
            if reg in ["RIP", "RSP", "RFLAGS", "CR0", "CR2", "CR3", "CR4"]:
                continue
            if len(reg) < 3:
                continue
            
            is_canonical = val < 0x0000800000000000 or val >= 0xFFFF800000000000
            if not is_canonical and val > 0:
                findings.append(
                    f"{reg} has non-canonical address 0x{val:016x} "
                    "(will cause #GP if accessed)"
                )
        
        # Check RSP
        if "RSP" in regs:
            rsp = regs["RSP"]
            if rsp == 0:
                findings.append("RSP is NULL! TSS may not be initialized.")
            elif rsp < 0x1000:
                findings.append(f"RSP suspiciously low: 0x{rsp:x}")
        
        return findings
    
    def _determine_cause(self, diagnosis: Diagnosis) -> str:
        """Determine probable cause based on analysis."""
        exc = diagnosis.exception
        
        # Use pattern diagnosis if available
        if diagnosis.matching_patterns:
            cause = diagnosis.matching_patterns[0].diagnosis
            if diagnosis.symbol:
                cause += f"\n\nLocation: {diagnosis.symbol.name}"
            return cause
        
        # Fallback based on exception type
        causes = {
            0x00: "Division by zero",
            0x06: "Invalid instruction (possibly SSE in kernel)",
            0x08: "Double fault - likely stack overflow or corrupted IDT",
            0x0D: "Protection violation - invalid segment or privileged instruction",
            0x0E: f"Page fault at address {exc.cr2 or 'unknown'}",
        }
        
        return causes.get(exc.vector, f"Unknown exception (vector {exc.vector})")
    
    def _generate_suggestions(self, diagnosis: Diagnosis) -> list[str]:
        """Generate fix suggestions."""
        suggestions = []
        exc = diagnosis.exception
        
        # Add pattern suggestions
        for pattern in diagnosis.matching_patterns:
            suggestions.append(pattern.solution)
        
        # Add symbol-based suggestions
        if diagnosis.symbol:
            suggestions.append(f"Check function '{diagnosis.symbol.name}'")
        
        # Add exception-specific suggestions
        if exc.vector == 0x0E and exc.cr2:
            try:
                cr2_addr = int(exc.cr2.replace("0x", ""), 16)
                if cr2_addr < 0x1000:
                    suggestions.append("NULL pointer dereference detected")
                elif cr2_addr & 0xFFF == 0:
                    suggestions.append("Unmapped page access (possible stack overflow)")
            except ValueError:
                pass
        
        if exc.vector == 0x06:
            suggestions.append("Run 'anvil inspect --check-sse' to find SSE instructions")
        
        if not suggestions:
            suggestions.append("Analyze log context for more information")
        
        return suggestions
    
    def print_diagnosis(self, diagnosis: Diagnosis) -> None:
        """Print formatted diagnosis."""
        console = Console()
        exc = diagnosis.exception
        
        # Header
        console.print()
        console.print(Panel(
            f"[bold red]💥 {exc.name} ({exc.code})[/bold red]",
            title="Crash Detected",
            border_style="red",
        ))
        
        # Basic info
        table = Table(show_header=False, box=None)
        table.add_column("Field", style="cyan")
        table.add_column("Value")
        
        if exc.rip:
            table.add_row("RIP", exc.rip)
        if exc.cr2:
            table.add_row("CR2", exc.cr2)
        if exc.rsp:
            table.add_row("RSP", exc.rsp)
        if diagnosis.symbol:
            table.add_row("Symbol", diagnosis.symbol.name)
        
        console.print(table)
        
        # Register analysis
        if diagnosis.register_analysis:
            console.print("\n[bold yellow]🔬 Register Analysis[/]")
            for finding in diagnosis.register_analysis:
                console.print(f"  • {finding}")
        
        # Cause
        console.print()
        console.print(Panel(
            diagnosis.probable_cause,
            title="[yellow]🔍 Probable Cause[/]",
            border_style="yellow",
        ))
        
        # Suggestions
        if diagnosis.suggestions:
            console.print("\n[cyan]💡 Suggestions:[/]")
            for i, suggestion in enumerate(diagnosis.suggestions, 1):
                console.print(f"  {i}. {suggestion}")
        
        # Disassembly
        if diagnosis.disassembly and diagnosis.disassembly.instructions:
            console.print("\n[magenta]📋 Code at RIP:[/]")
            
            rip = 0
            if exc.rip:
                try:
                    rip = int(exc.rip.replace("RIP=", "").replace("0x", ""), 16)
                except ValueError:
                    pass
            
            for addr, _, asm in diagnosis.disassembly.instructions[:10]:
                marker = "→" if addr == rip else " "
                style = "bold red" if addr == rip else "dim"
                console.print(f"  {marker} [{style}]0x{addr:016x}: {asm}[/{style}]")
        
        # Matching patterns
        if diagnosis.matching_patterns:
            console.print("\n[blue]📚 Known Patterns:[/]")
            for pattern in diagnosis.matching_patterns:
                color = {
                    Severity.INFO: "blue",
                    Severity.WARNING: "yellow",
                    Severity.CRITICAL: "red",
                }[pattern.severity]
                console.print(f"  • [{color}]{pattern.name}[/{color}]")
        
        console.print()

