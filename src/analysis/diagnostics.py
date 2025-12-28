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

from core.config import AnvilConfig
from core.paths import PathResolver
from core.logger import console
from analysis.exception_detector import CpuException, ExceptionContext
from analysis.binary_inspector import BinaryInspector, Disassembly, Symbol
from analysis.patterns import find_matching_patterns, Pattern, Severity
from runner.streams import LogEntry


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
        crash_info,  # CrashInfo from runner.monitor
    ) -> Diagnosis:
        """
        Analisa crash e gera diagnóstico completo.
        """
        from analysis.exception_detector import CpuException
        
        # Criar CpuException a partir do CrashInfo
        exception = CpuException(
            timestamp=crash_info.timestamp,
            vector=0,  # Será determinado pelo código abaixo
            name=crash_info.exception_type,
            code=crash_info.exception_code,
            rip=crash_info.rip,
            cr2=crash_info.cr2,
            raw_line="",
        )
        
        # Mapear código para vector
        code_to_vector = {
            "#DE": 0x00, "#UD": 0x06, "#DF": 0x08, 
            "#GP": 0x0D, "#PF": 0x0E,
        }
        exception.vector = code_to_vector.get(crash_info.exception_code, 0)
        
        context = crash_info.context_lines
        
        diagnosis = Diagnosis(
            timestamp=datetime.now(),
            exception=exception,
            context_lines=context,
        )
        
        # 1. Buscar padrões conhecidos
        context_text = "\n".join(e.line for e in context)
        diagnosis.matching_patterns = find_matching_patterns(context_text)
        
        # 2. Localizar símbolo no RIP
        if exception.rip:
            try:
                rip_str = exception.rip.replace("RIP=", "").replace("0x", "")
                rip_addr = int(rip_str, 16)
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
    
    def _analyze_registers(self, cpu_context: list[LogEntry], rip: Optional[str]) -> list[str]:
        """Analisa valores dos registradores em busca de anomalias."""
        findings = []
        import re
        
        # Encontrar último dump de registradores
        last_regs = {}
        for entry in reversed(cpu_context):
            # Parsear linha: RAX=... RBX=...
            matches = re.findall(r'([R|E][A-Z0-9]+)=([0-9a-fA-F]+)', entry.line)
            for reg, val in matches:
                if reg not in last_regs:
                    try:
                        last_regs[reg] = int(val, 16)
                    except ValueError:
                        pass
            
            # Se já achamos RIP e RAX, provavelmente temos um set completo
            if "RIP" in last_regs and "RAX" in last_regs:
                break
        
        if not last_regs:
            return []
            
        # 1. Null Pointers
        # Apenas registradores que costumam ser ponteiros em contextos onde 0 é inválido
        for reg in ["RAX", "RBX", "RCX", "RDX", "RSI", "RDI", "RBP", "R8", "R9", "R10", "R11", "R12", "R13", "R14", "R15"]:
            if reg in last_regs and last_regs[reg] == 0:
                findings.append(f"Registrador [bold]{reg}[/bold] é NULL (0x0). Se for usado como ponteiro, causará crash.")

        # 2. Ponteiros suspeitos (não canônicos)
        # Faixa buraco: 0x0000_8000_0000_0000 até 0xFFFF_7FFF_FFFF_FFFF
        for reg, val in last_regs.items():
            if reg in ["RIP", "RSP", "RFLAGS", "EFLAGS", "CR0", "CR2", "CR3", "CR4"]: continue
            if len(reg) < 3: continue # Ignorar CS, SS, etc
            
            is_canonical = False
            if val < 0x0000800000000000: is_canonical = True
            elif val >= 0xFFFF800000000000: is_canonical = True
            
            if not is_canonical and val > 0:
                 findings.append(f"Registrador [bold]{reg}[/bold] tem endereço não-canônico: 0x{val:016x} (Causa imediata de #GP se acessado)")

        # 3. Stack Pointer inválido
        if "RSP" in last_regs:
            rsp = last_regs["RSP"]
            if rsp == 0:
                findings.append("Stack Pointer (RSP) é NULL!")
            elif rsp < 0x1000: 
                 findings.append(f"Stack Pointer (RSP) suspeitosamente baixo: 0x{rsp:x}")

        return findings

    def _colorize_line(self, line: str) -> str:
        """Aplica cores às tags conhecidas (mesma lógica do Monitor)."""
        import re
        ansi_escape = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]')
        line = ansi_escape.sub('', line)
        
        line = re.sub(r'\[OK\]', '[green][OK][/green]', line)
        line = re.sub(r'\[FAIL\]', '[red bold][FAIL][/red bold]', line)
        line = re.sub(r'\[JUMP\]', '[magenta][JUMP][/magenta]', line)
        line = re.sub(r'\[DEBUG\]', '[dim][DEBUG][/dim]', line)
        line = re.sub(r'\[INFO\]', '[cyan][INFO][/cyan]', line)
        line = re.sub(r'\[WARN\]', '[yellow][WARN][/yellow]', line)
        line = re.sub(r'\[ERROR\]', '[red][ERROR][/red]', line)
        return line

    def print_full_crash_report(
        self,
        diagnosis: Diagnosis,
        crash_list: list,  # list[CrashInfo]
        serial_context: list[LogEntry],
        cpu_context: list[LogEntry],
    ) -> None:
        """
        Imprime relatório completo de crash com análise detalhada.
        
        Inclui:
        - Timeline de exceções
        - Contexto serial antes do crash
        - Análise do CPU log
        - Padrões detectados
        - Causa provável e sugestões
        """
        from rich.panel import Panel
        from rich.table import Table
        
        exc = diagnosis.exception
        
        # ====================================================================
        # CABEÇALHO
        # ====================================================================
        console.print()
        console.print(Panel(
            f"[bold red]💥 RELATÓRIO DE CRASH - {exc.name} ({exc.code})[/bold red]",
            border_style="red",
            title="Análise Completa",
        ))
        
        # ====================================================================
        # TIMELINE DE EXCEÇÕES
        # ====================================================================
        if len(crash_list) > 1:
            console.print("\n[bold cyan]📊 Timeline de Exceções[/bold cyan]")
            for i, crash in enumerate(crash_list, 1):
                ts = crash.timestamp.strftime("%H:%M:%S.%f")[:-3]
                console.print(f"  {i}. [{ts}] {crash}")
        
        # ====================================================================
        # INFORMAÇÕES DO CRASH PRINCIPAL
        # ====================================================================
        console.print("\n[bold cyan]🔍 Detalhes da Exceção[/bold cyan]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Campo", style="yellow")
        table.add_column("Valor", style="white")
        
        table.add_row("Tipo", f"{exc.name} ({exc.code})")
        if exc.rip:
            table.add_row("RIP", exc.rip)
        if exc.cr2:
            table.add_row("CR2", exc.cr2)
        if exc.rsp:
            table.add_row("RSP", exc.rsp)
        if diagnosis.symbol:
            table.add_row("Símbolo", diagnosis.symbol.name)
            if diagnosis.symbol.file:
                table.add_row("Arquivo", f"{diagnosis.symbol.file}:{diagnosis.symbol.line or '?'}")
        
        console.print(table)
        
        # Análise extra de registradores
        reg_analysis = self._analyze_registers(cpu_context, exc.rip)
        if reg_analysis:
            console.print("\n[bold yellow]🔬 Análise de Registradores[/bold yellow]")
            for analysis in reg_analysis:
                console.print(f"  • {analysis}")
        
        # ====================================================================
        # SAÍDA SERIAL ANTES DO CRASH
        # ====================================================================
       # if serial_context:
       #     console.print("\n[bold cyan]📺 Últimas Linhas Serial (antes do crash)[/bold cyan]")
        #    console.print("[dim]─" * 60 + "[/dim]")
       #     # Aumentado para 50 linhas para dar mais contexto
       #     for entry in serial_context[-50:]:
        #        colored = self._colorize_line(entry.line)
        #        console.print(f"  {colored}")
       #     console.print("[dim]─" * 60 + "[/dim]")
        
        # ====================================================================
        # ANÁLISE DO CPU LOG
        # ====================================================================
        if cpu_context:
            console.print("\n[bold cyan]🖥️ Contexto CPU (registradores)[/bold cyan]")
            # Filtrar linhas relevantes (RIP, RSP, registradores, etc.)
            relevant_lines = []
            # Aumentado busca para 200 linhas
            for entry in cpu_context[-400:]:
                line = entry.line
                # Filtro mais permissivo ou apenas mostrar últimas N linhas se filtro for muito agressivo
                # O usuário pediu mais info, vamos mostrar blocos contíguos de registradores
                if any(kw in line.upper() for kw in ["RIP=", "RSP=", "RAX=", "RBX=", "RCX=", "RDX=", 
                                                       "RSI=", "RDI=", "R8=", "R9=", "R10=", "R11=",
                                                       "CR0=", "CR2=", "CR3=", "CR4=", "EFLAGS=",
                                                       "CS=", "SS=", "DS=", "ES=", "FS=", "GS=",
                                                       "SMM=", "V="]):
                    relevant_lines.append(line)
            
            if relevant_lines:
                # Mostrar mais linhas (últimas 40 em vez de 20)
                for line in relevant_lines[-40:]:
                    console.print(f"  [dim]{line}[/dim]")
        
        # ====================================================================
        # DISASSEMBLY
        # ====================================================================
        if diagnosis.disassembly and diagnosis.disassembly.instructions:
            console.print("\n[bold cyan]📋 Código no RIP[/bold cyan]")
            
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
        
        # ====================================================================
        # PADRÕES CONHECIDOS
        # ====================================================================
        #if diagnosis.matching_patterns:
        #    console.print("\n[bold cyan]📚 Padrões Conhecidos Detectados[/bold cyan]")
        #    for pattern in diagnosis.matching_patterns:
        #        severity_color = {
        #            Severity.INFO: "blue",
        #            Severity.WARNING: "yellow",
        #            Severity.CRITICAL: "red",
        #        }[pattern.severity]
        #        console.print(f"  • [{severity_color}]{pattern.name}[/{severity_color}]")
        #        console.print(f"    [dim]{pattern.diagnosis}[/dim]")
        
        # ====================================================================
        # CAUSA PROVÁVEL
        # ====================================================================
       # console.print("\n[bold yellow]🎯 Causa Provável[/bold yellow]")
       # console.print(Panel(
      #      diagnosis.probable_cause,
       #     border_style="yellow",
       # ))
        
        # ====================================================================
        # SUGESTÕES
        # ====================================================================
     #   if diagnosis.suggestions:
      #      console.print("\n[bold green]💡 Sugestões de Correção[/bold green]")
      #      for i, suggestion in enumerate(diagnosis.suggestions, 1):
      #          console.print(f"  {i}. {suggestion}")
        
        # ====================================================================
        # PRÓXIMOS PASSOS
        # ====================================================================
      #  console.print("\n[bold magenta]🔧 Próximos Passos Recomendados[/bold magenta]")
     #   console.print("  1. Executar 'anvil run --gdb' para debug interativo")
     #   console.print("  2. Verificar logs em: anvil/src/logs/...")
      #  console.print("  3. Analisar binário: 'anvil inspect kernel'")
        
       # console.print()

