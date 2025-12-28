"""
Anvil Analysis - Padrões conhecidos de erros
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Severity(Enum):
    """Severidade do problema."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Pattern:
    """Padrão de erro conhecido."""
    name: str
    trigger: str  # Regex pattern
    diagnosis: str
    solution: str
    severity: Severity = Severity.WARNING
    
    _compiled: Optional[re.Pattern] = None
    
    def __post_init__(self):
        self._compiled = re.compile(self.trigger, re.IGNORECASE)
    
    def matches(self, text: str) -> bool:
        """Verifica se texto corresponde ao padrão."""
        if self._compiled:
            return bool(self._compiled.search(text))
        return False


# Padrões conhecidos do RedstoneOS
KNOWN_PATTERNS = {
    # ========================================================================
    # Exceções de CPU
    # ========================================================================
    
    "page_fault": Pattern(
        name="page_fault",
        trigger=r"v=0e|check_exception.*0xe",
        diagnosis="Page Fault (#PF) - Acesso a memória não mapeada ou protegida",
        solution="Verificar CR2 para o endereço faltante. Causas comuns: ponteiro nulo, "
                 "stack overflow, heap corrompido, endereço não mapeado.",
        severity=Severity.CRITICAL,
    ),
    
    "general_protection": Pattern(
        name="general_protection",
        trigger=r"v=0d|check_exception.*0xd",
        diagnosis="General Protection Fault (#GP) - Violação de proteção",
        solution="Causas comuns: seletor de segmento inválido, instrução privilegiada em "
                 "modo usuário, desalinhamento de acesso, ou instrução ilegal.",
        severity=Severity.CRITICAL,
    ),
    
    "double_fault": Pattern(
        name="double_fault",
        trigger=r"v=08|check_exception.*0x8",
        diagnosis="Double Fault (#DF) - Exceção durante tratamento de exceção",
        solution="Geralmente causado por stack overflow no kernel ou IDT corrompida. "
                 "Verificar se há recursão infinita ou stack muito pequena.",
        severity=Severity.CRITICAL,
    ),
    
    "invalid_opcode": Pattern(
        name="invalid_opcode",
        trigger=r"v=06|check_exception.*0x6",
        diagnosis="Invalid Opcode (#UD) - Instrução inválida",
        solution="Causas comuns: instrução SSE/AVX em código de kernel (proibido), "
                 "código corrompido, salto para dados, ou CPU não suporta instrução.",
        severity=Severity.CRITICAL,
    ),
    
    "divide_error": Pattern(
        name="divide_error",
        trigger=r"v=00|check_exception.*0x0",
        diagnosis="Divide Error (#DE) - Divisão por zero ou overflow",
        solution="Verificar operações de divisão. Pode ser divisão por zero literal "
                 "ou resultado que não cabe no registrador de destino.",
        severity=Severity.CRITICAL,
    ),
    
    # ========================================================================
    # Problemas do RedstoneOS
    # ========================================================================
    
    "sse_in_kernel": Pattern(
        name="sse_in_kernel",
        trigger=r"v=06.*RIP=ffffffff|#UD.*kernel",
        diagnosis="Instrução SSE/AVX detectada em código do kernel",
        solution="O kernel RedstoneOS proíbe SSE/AVX. Verificar:\n"
                 "  1. Target x86_64-redstone.json tem soft-float\n"
                 "  2. Não há operações com f32/f64\n"
                 "  3. Usar 'objdump -d kernel | grep -E \"xmm|ymm\"' para encontrar",
        severity=Severity.CRITICAL,
    ),
    
    "stack_overflow_guard": Pattern(
        name="stack_overflow_guard",
        trigger=r"v=0e.*guard|CR2=.*0{6,}",
        diagnosis="Stack overflow - Hit na guard page",
        solution="Stack do kernel esgotada. Causas:\n"
                 "  1. Recursão infinita ou excessiva\n"
                 "  2. Alocação grande na stack (usar heap)\n"
                 "  3. Stack inicial muito pequena",
        severity=Severity.CRITICAL,
    ),
    
    "null_pointer": Pattern(
        name="null_pointer",
        trigger=r"v=0e.*CR2=0{8,16}|CR2=0x0[^0-9a-fA-F]",
        diagnosis="Null pointer dereference",
        solution="Acesso a ponteiro nulo. Verificar:\n"
                 "  1. Option/Result não tratados\n"
                 "  2. Ponteiros não inicializados\n"
                 "  3. Use-after-free",
        severity=Severity.CRITICAL,
    ),
    
    "heap_corruption": Pattern(
        name="heap_corruption",
        trigger=r"slab.*corrupt|heap.*invalid|alloc.*fail",
        diagnosis="Corrupção no heap allocator",
        solution="Possível double-free, use-after-free, ou buffer overflow. "
                 "Verificar alocações e dealocações recentes.",
        severity=Severity.CRITICAL,
    ),
    
    "timer_storm": Pattern(
        name="timer_storm",
        trigger=r"(INT=0x20.*){10,}|timer.*overflow",
        diagnosis="Timer IRQ storm - Interrupções excessivas",
        solution="Timer pode estar configurado com frequência muito alta ou "
                 "handler não está limpando a interrupção corretamente.",
        severity=Severity.WARNING,
    ),
    
    "iret_corruption": Pattern(
        name="iret_corruption",
        trigger=r"iret.*invalid|v=0d.*iret",
        diagnosis="Stack frame do IRET corrompido",
        solution="O frame de interrupção na stack está corrompido. Verificar:\n"
                 "  1. Handler de interrupção modifica stack incorretamente\n"
                 "  2. Stack overflow durante interrupção\n"
                 "  3. Preempção incorreta",
        severity=Severity.CRITICAL,
    ),
    
    # ========================================================================
    # Avisos
    # ========================================================================
    
    "unimplemented_msr": Pattern(
        name="unimplemented_msr",
        trigger=r"unimplemented.*msr|ignored.*msr",
        diagnosis="MSR não implementado no QEMU",
        solution="O kernel está usando um MSR que o QEMU não suporta. "
                 "Geralmente seguro ignorar se não causar crash.",
        severity=Severity.INFO,
    ),
    
    "cr0_flip": Pattern(
        name="cr0_flip",
        trigger=r"CR0.*update.*(WP|PE).*multiple|CR0.*(clear|set){2,}",
        diagnosis="CR0.WP sendo alterado frequentemente",
        solution="O kernel está alternando proteção de escrita. "
                 "Pode indicar copy-on-write ou bug em mapeamento.",
        severity=Severity.WARNING,
    ),
}


def find_matching_patterns(text: str) -> list[Pattern]:
    """Encontra todos os padrões que correspondem ao texto."""
    matches = []
    for pattern in KNOWN_PATTERNS.values():
        if pattern.matches(text):
            matches.append(pattern)
    return matches
