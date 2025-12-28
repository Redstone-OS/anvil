"""
Anvil Analysis - Engine de diagnóstico inteligente
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from anvil.core.config import AnvilConfig
from anvil.core.paths import PathResolver
from anvil.core.logger import console
from anvil.analysis.exception_detector import CpuException, ExceptionContext
from anvil.analysis.binary_inspector import BinaryInspector, Disassembly, Symbol
from anvil.analysis.patterns import find_matching_patterns, Pattern, Severity
from anvil.runner.streams import LogEntry


@dataclass
class Diagnosis:
    """Resultado do diagnóstico."""
    timestamp: datetime
    exception: CpuException
    
    # Análise
    symbol: Optional[Symbol] = None
    disassembly: Optional[Disassembly] = None
    matching_patterns: list[Pattern] = field(default_factory=list)
    
    # Conclusões
    probable_cause: str = ""
    suggestions: list[str] = field(default_factory=list)
    severity: Severity = Severity.CRITICAL
    
    # Contexto adicional
    context_lines: list[LogEntry] = field(default_factory=list)
    extra_info: dict = field(default_factory=dict)


class DiagnosticEngine:
    """
    Engine inteligente de diagnóstico.
    
    Pipeline:
    1. Identifica tipo de exceção
    2. Extrai contexto (RIP, stack, registros)
    3. Desmonta código no RIP
    4. Encontra símbolo/função
    5. Analisa padrões conhecidos
    6. Verifica binário por problemas relacionados
    7. Gera diagnóstico com causa provável e sugestões
    """
    
    def __init__(self, paths: PathResolver, config: AnvilConfig):
        self.paths = paths
        self.config = config
        self.inspector = BinaryInspector(paths)
    
    async def analyze_crash(
        self,
        exception: CpuException,
        context: list[LogEntry],
    ) -> Diagnosis:
        """
        Analisa crash e gera diagnóstico completo.
        """
        diagnosis = Diagnosis(
            timestamp=datetime.now(),
            exception=exception,
            context_lines=context,
        )
        
        # 1. Buscar padrões conhecidos
        context_text = "\n".join(e.line for e in context)
        diagnosis.matching_patterns = find_matching_patterns(context_text)
        
        # Adicionar padrão da exceção se não encontrado
        if exception.raw_line:
            exc_patterns = find_matching_patterns(exception.raw_line)
            for p in exc_patterns:
                if p not in diagnosis.matching_patterns:
                    diagnosis.matching_patterns.append(p)
        
        # 2. Localizar símbolo no RIP
        if exception.rip:
            try:
                rip_addr = int(exception.rip.replace("0x", ""), 16)
                kernel_path = self.paths.kernel_binary()
                
                if kernel_path.exists():
                    diagnosis.symbol = await self.inspector.find_symbol_at(
                        kernel_path, rip_addr
                    )
                    
                    # 3. Desmontar código
                    diagnosis.disassembly = await self.inspector.disassemble_at(
                        kernel_path, rip_addr
                    )
            except ValueError:
                pass
        
        # 4. Determinar causa provável
        diagnosis.probable_cause = self._determine_cause(diagnosis)
        diagnosis.suggestions = self._generate_suggestions(diagnosis)
        
        # 5. Determinar severidade
        if diagnosis.matching_patterns:
            max_severity = max(p.severity for p in diagnosis.matching_patterns)
            diagnosis.severity = max_severity
        
        return diagnosis
    
    def _determine_cause(self, diagnosis: Diagnosis) -> str:
        """Determina causa provável baseado na análise."""
        exc = diagnosis.exception
        
        # Usar padrão correspondente se disponível
        if diagnosis.matching_patterns:
            pattern = diagnosis.matching_patterns[0]
            cause = pattern.diagnosis
            
            # Adicionar informação de localização
            if diagnosis.symbol:
                cause += f"\n\nLocalização: {diagnosis.symbol.name}"
            
            return cause
        
        # Fallback baseado no tipo de exceção
        causes = {
            0x00: "Divisão por zero",
            0x06: "Instrução inválida (possivelmente SSE em código kernel)",
            0x08: "Double fault - provavelmente stack overflow ou IDT corrompida",
            0x0D: "Violação de proteção - segmento inválido ou instrução privilegiada",
            0x0E: f"Page fault no endereço {exc.cr2 or 'desconhecido'}",
        }
        
        return causes.get(exc.vector, f"Exceção desconhecida (vector {exc.vector})")
    
    def _generate_suggestions(self, diagnosis: Diagnosis) -> list[str]:
        """Gera sugestões de correção."""
        suggestions = []
        exc = diagnosis.exception
        
        # Sugestões dos padrões
        for pattern in diagnosis.matching_patterns:
            suggestions.append(pattern.solution)
        
        # Sugestões adicionais baseadas no contexto
        if diagnosis.symbol:
            suggestions.append(
                f"Verificar código da função '{diagnosis.symbol.name}'"
            )
        
        if exc.vector == 0x0E and exc.cr2:
            # Page fault
            try:
                cr2_addr = int(exc.cr2.replace("0x", ""), 16)
                if cr2_addr < 0x1000:
                    suggestions.append("NULL pointer dereference detectado")
                elif cr2_addr & 0xFFF == 0:
                    suggestions.append("Acesso a página não mapeada (possível stack overflow)")
            except ValueError:
                pass
        
        if exc.vector == 0x06:
            suggestions.append("Executar 'anvil inspect kernel --check-sse' para verificar instruções SSE")
        
        if not suggestions:
            suggestions.append("Analisar contexto do log para mais informações")
        
        return suggestions
    
    def print_diagnosis(self, diagnosis: Diagnosis) -> None:
        """Imprime diagnóstico formatado."""
        exc = diagnosis.exception
        
        # Header
        console.print()
        console.print(Panel(
            f"[bold red]💥 {exc.name} ({exc.code})[/bold red]",
            title="Crash Detectado",
            border_style="red",
        ))
        
        # Informações básicas
        table = Table(show_header=False, box=None)
        table.add_column("Campo", style="cyan")
        table.add_column("Valor")
        
        if exc.rip:
            table.add_row("RIP", exc.rip)
        if exc.cr2:
            table.add_row("CR2", exc.cr2)
        if exc.rsp:
            table.add_row("RSP", exc.rsp)
        if diagnosis.symbol:
            table.add_row("Símbolo", diagnosis.symbol.name)
        
        console.print(table)
        
        # Causa provável
        console.print()
        console.print(Panel(
            diagnosis.probable_cause,
            title="[yellow]🔍 Causa Provável[/yellow]",
            border_style="yellow",
        ))
        
        # Sugestões
        if diagnosis.suggestions:
            console.print()
            console.print("[cyan]💡 Sugestões:[/cyan]")
            for i, suggestion in enumerate(diagnosis.suggestions, 1):
                console.print(f"  {i}. {suggestion}")
        
        # Disassembly
        if diagnosis.disassembly and diagnosis.disassembly.instructions:
            console.print()
            console.print("[magenta]📋 Código no RIP:[/magenta]")
            
            rip = 0
            if exc.rip:
                try:
                    rip = int(exc.rip.replace("0x", ""), 16)
                except ValueError:
                    pass
            
            for addr, _, asm in diagnosis.disassembly.instructions[:10]:
                marker = "→" if addr == rip else " "
                style = "bold red" if addr == rip else ""
                console.print(f"  {marker} [{style}]0x{addr:016x}: {asm}[/{style}]")
        
        # Padrões correspondentes
        if diagnosis.matching_patterns:
            console.print()
            console.print("[blue]📚 Padrões Correspondentes:[/blue]")
            for pattern in diagnosis.matching_patterns:
                severity_color = {
                    Severity.INFO: "blue",
                    Severity.WARNING: "yellow",
                    Severity.CRITICAL: "red",
                }[pattern.severity]
                console.print(f"  • [{severity_color}]{pattern.name}[/{severity_color}]: {pattern.diagnosis}")
        
        console.print()
