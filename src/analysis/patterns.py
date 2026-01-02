"""Anvil Analysis - Known error patterns."""

from __future__ import annotations

import re
import functools
from dataclasses import dataclass
from enum import Enum
from typing import Optional


# Severity ordering for comparison
_SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}


@functools.total_ordering
class Severity(Enum):
    """Pattern severity level."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    
    def __lt__(self, other: Severity) -> bool:
        if isinstance(other, Severity):
            return _SEVERITY_ORDER[self.value] < _SEVERITY_ORDER[other.value]
        return NotImplemented
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Severity):
            return self.value == other.value
        return NotImplemented
    
    def __hash__(self) -> int:
        return hash(self.value)


@dataclass
class Pattern:
    """Known error pattern for automatic diagnosis."""
    name: str
    trigger: str  # Regex pattern
    diagnosis: str
    solution: str
    severity: Severity = Severity.WARNING
    
    _compiled: Optional[re.Pattern] = None
    
    def __post_init__(self) -> None:
        self._compiled = re.compile(self.trigger, re.IGNORECASE)
    
    def matches(self, text: str) -> bool:
        """Check if text matches this pattern."""
        if self._compiled:
            return bool(self._compiled.search(text))
        return False


# ============================================================================
# Known RedstoneOS Error Patterns
# ============================================================================

KNOWN_PATTERNS: dict[str, Pattern] = {
    # -------------------------------------------------------------------------
    # CPU Exceptions
    # -------------------------------------------------------------------------
    
    "page_fault": Pattern(
        name="page_fault",
        trigger=r"v=0e|check_exception.*0xe",
        diagnosis="Page Fault (#PF) - Access to unmapped or protected memory",
        solution=(
            "Check CR2 for the faulting address. Common causes:\n"
            "  - NULL pointer dereference\n"
            "  - Stack overflow (unmapped guard page)\n"
            "  - Use-after-free / heap corruption\n"
            "  - Accessing non-canonical address"
        ),
        severity=Severity.CRITICAL,
    ),
    
    "general_protection": Pattern(
        name="general_protection",
        trigger=r"v=0d|check_exception.*0xd",
        diagnosis="General Protection Fault (#GP) - Protection violation",
        solution=(
            "Common causes:\n"
            "  - Invalid segment selector\n"
            "  - Privileged instruction in user mode\n"
            "  - Misaligned memory access\n"
            "  - Non-canonical address in register"
        ),
        severity=Severity.CRITICAL,
    ),
    
    "double_fault": Pattern(
        name="double_fault",
        trigger=r"v=08|check_exception.*0x8",
        diagnosis="Double Fault (#DF) - Exception during exception handling",
        solution=(
            "Usually caused by:\n"
            "  - Kernel stack overflow\n"
            "  - Corrupted IDT\n"
            "  - Corrupted TSS\n"
            "Check if IST is configured for the double fault handler."
        ),
        severity=Severity.CRITICAL,
    ),
    
    "invalid_opcode": Pattern(
        name="invalid_opcode",
        trigger=r"v=06|check_exception.*0x6",
        diagnosis="Invalid Opcode (#UD) - Illegal instruction",
        solution=(
            "Common causes:\n"
            "  - SSE/AVX instruction in kernel (use soft-float)\n"
            "  - Corrupted code section\n"
            "  - Jump to data or unmapped memory\n"
            "  - CPU doesn't support the instruction\n"
            "Run 'anvil inspect --check-sse' to find SSE violations."
        ),
        severity=Severity.CRITICAL,
    ),
    
    "divide_error": Pattern(
        name="divide_error",
        trigger=r"v=00|check_exception.*0x0",
        diagnosis="Divide Error (#DE) - Division by zero or overflow",
        solution=(
            "Check division operations near RIP:\n"
            "  - DIV/IDIV with zero divisor\n"
            "  - Result doesn't fit in destination register"
        ),
        severity=Severity.CRITICAL,
    ),
    
    # -------------------------------------------------------------------------
    # RedstoneOS-Specific Patterns
    # -------------------------------------------------------------------------
    
    "sse_in_kernel": Pattern(
        name="sse_in_kernel",
        trigger=r"v=06.*RIP=ffffffff|#UD.*kernel",
        diagnosis="SSE/AVX instruction detected in kernel code",
        solution=(
            "RedstoneOS kernel prohibits SSE/AVX. Check:\n"
            "  1. Target x86_64-redstone.json uses soft-float\n"
            "  2. No f32/f64 operations in kernel code\n"
            "  3. Use 'objdump -d kernel | grep -E \"xmm|ymm\"' to find"
        ),
        severity=Severity.CRITICAL,
    ),
    
    "stack_overflow_guard": Pattern(
        name="stack_overflow_guard",
        trigger=r"v=0e.*guard|CR2=.*0{6,}",
        diagnosis="Stack overflow - Hit guard page",
        solution=(
            "Kernel stack exhausted. Causes:\n"
            "  - Infinite or deep recursion\n"
            "  - Large stack allocations (use heap instead)\n"
            "  - Initial stack too small"
        ),
        severity=Severity.CRITICAL,
    ),
    
    "null_pointer": Pattern(
        name="null_pointer",
        trigger=r"v=0e.*CR2=0{8,16}|CR2=0x0[^0-9a-fA-F]",
        diagnosis="NULL pointer dereference",
        solution=(
            "Accessing address 0x0. Check:\n"
            "  - Unwrapped Option::None\n"
            "  - Uninitialized pointer\n"
            "  - Use-after-free returning null"
        ),
        severity=Severity.CRITICAL,
    ),
    
    "rsp_null": Pattern(
        name="rsp_null",
        trigger=r"RSP=0{16}|RSP is NULL",
        diagnosis="Stack pointer is NULL",
        solution=(
            "RSP = 0 indicates:\n"
            "  - TSS not properly initialized\n"
            "  - Corrupted interrupt frame\n"
            "  - Missing kernel stack in privilege_stack_table[0]"
        ),
        severity=Severity.CRITICAL,
    ),
    
    # -------------------------------------------------------------------------
    # Warnings (non-fatal)
    # -------------------------------------------------------------------------
    
    "timer_storm": Pattern(
        name="timer_storm",
        trigger=r"(INT=0x20.*){10,}|timer.*overflow",
        diagnosis="Timer IRQ storm - Excessive interrupts",
        solution=(
            "Timer configured too fast or handler not ACKing properly. "
            "Check PIT/APIC timer frequency and EOI."
        ),
        severity=Severity.WARNING,
    ),
    
    "unimplemented_msr": Pattern(
        name="unimplemented_msr",
        trigger=r"unimplemented.*msr|ignored.*msr",
        diagnosis="Unimplemented MSR accessed",
        solution=(
            "The kernel is using an MSR that QEMU doesn't support. "
            "Usually safe to ignore if not causing crashes."
        ),
        severity=Severity.INFO,
    ),
}


def find_patterns(text: str) -> list[Pattern]:
    """Find all matching patterns in text."""
    return [p for p in KNOWN_PATTERNS.values() if p.matches(text)]

