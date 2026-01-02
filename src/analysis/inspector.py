"""Anvil Analysis - Binary inspection and disassembly."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.paths import Paths
from core.logger import Logger, get_logger
from runner.wsl import WslExecutor


@dataclass
class Symbol:
    """Symbol from binary."""
    name: str
    address: int
    size: int = 0
    symbol_type: str = ""
    file: Optional[str] = None
    line: Optional[int] = None
    
    def __str__(self) -> str:
        loc = f" ({self.file}:{self.line})" if self.file else ""
        return f"{self.name} @ 0x{self.address:016x}{loc}"


@dataclass
class Section:
    """Binary section."""
    name: str
    address: int
    size: int
    flags: str = ""


@dataclass
class Disassembly:
    """Disassembly result."""
    address: int
    instructions: list[tuple[int, str, str]]  # (addr, bytes, asm)
    symbol: Optional[Symbol] = None


@dataclass
class SseViolation:
    """SSE instruction found in kernel."""
    address: int
    instruction: str
    context: str = ""
    symbol: Optional[str] = None


class BinaryInspector:
    """
    Binary inspection using WSL tools.
    
    Uses objdump, nm, addr2line to:
    - Disassemble code at specific addresses
    - Find symbols for addresses
    - Detect forbidden SSE/AVX instructions
    """
    
    # SSE/AVX instruction patterns
    SSE_PATTERNS = [
        r"\b(movaps|movups|movss|movsd)\b",
        r"\b(addps|addss|subps|subss|mulps|mulss|divps|divss)\b",
        r"\b(xmm[0-9]+|ymm[0-9]+|zmm[0-9]+)\b",
        r"\b(vmov|vadd|vsub|vmul|vdiv)\w*\b",
        r"\b(pxor|movdqa|movdqu|paddd|psubd)\b",
    ]
    
    def __init__(
        self,
        paths: Paths,
        log: Optional[Logger] = None,
    ):
        self.paths = paths
        self.log = log or get_logger()
        self.wsl = WslExecutor()
        self._sse_regex = re.compile("|".join(self.SSE_PATTERNS), re.IGNORECASE)
    
    async def disassemble_at(
        self,
        binary: Path,
        address: int,
        context: int = 20,
    ) -> Optional[Disassembly]:
        """
        Disassemble code around an address.
        
        Args:
            binary: Path to binary file
            address: Target address
            context: Number of instructions of context
        
        Returns:
            Disassembly with instructions, or None on failure
        """
        wsl_path = Paths.to_wsl(binary)
        
        # Calculate range (assume ~4 bytes per instruction)
        start = max(0, address - context * 4)
        end = address + context * 4
        
        cmd = (
            f"objdump -d --no-show-raw-insn "
            f"--start-address=0x{start:x} "
            f"--stop-address=0x{end:x} "
            f"'{wsl_path}'"
        )
        
        result = await self.wsl.run(cmd)
        
        if not result.success:
            self.log.warning(f"objdump failed: {result.stderr}")
            return None
        
        instructions = []
        current_symbol = None
        
        for line in result.stdout.split("\n"):
            # Detect symbol
            if line.endswith(">:"):
                match = re.search(r"<(.+)>:", line)
                if match:
                    current_symbol = match.group(1)
            
            # Parse instruction
            match = re.match(r"\s*([0-9a-f]+):\s+(.+)", line, re.IGNORECASE)
            if match:
                addr = int(match.group(1), 16)
                asm = match.group(2).strip()
                instructions.append((addr, "", asm))
        
        symbol = None
        if current_symbol:
            symbol = Symbol(name=current_symbol, address=address)
        
        return Disassembly(
            address=address,
            instructions=instructions,
            symbol=symbol,
        )
    
    async def find_symbol(
        self,
        binary: Path,
        address: int,
    ) -> Optional[Symbol]:
        """Find symbol at address using addr2line."""
        wsl_path = Paths.to_wsl(binary)
        
        # Try addr2line first (more accurate)
        cmd = f"addr2line -C -f -e '{wsl_path}' 0x{address:x}"
        result = await self.wsl.run(cmd)
        
        if result.success and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            
            if len(lines) >= 2:
                func_name = lines[0]
                file_info = lines[1]
                
                if func_name != "??" and func_name:
                    file_path = None
                    line_num = None
                    
                    if ":" in file_info:
                        parts = file_info.rsplit(":", 1)
                        if len(parts) == 2 and parts[1].isdigit():
                            file_path = parts[0]
                            line_num = int(parts[1])
                    
                    return Symbol(
                        name=func_name,
                        address=address,
                        file=file_path,
                        line=line_num,
                    )
        
        # Fallback: nm with manual search
        cmd = f"nm -C '{wsl_path}' | sort -k1"
        result = await self.wsl.run(cmd)
        
        if not result.success:
            return None
        
        best_match = None
        best_addr = 0
        
        for line in result.stdout.split("\n"):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    sym_addr = int(parts[0], 16)
                    sym_name = parts[2]
                    
                    if sym_addr <= address and sym_addr > best_addr:
                        best_addr = sym_addr
                        best_match = Symbol(
                            name=sym_name,
                            address=sym_addr,
                            symbol_type=parts[1],
                        )
                except ValueError:
                    continue
        
        return best_match
    
    async def check_sse(self, binary: Path) -> list[SseViolation]:
        """
        Scan binary for forbidden SSE/AVX instructions.
        
        Returns list of violations found.
        """
        self.log.info(f"🔍 Scanning {binary.name} for SSE/AVX...")
        
        wsl_path = Paths.to_wsl(binary)
        cmd = f"objdump -d '{wsl_path}'"
        
        result = await self.wsl.run(cmd)
        
        if not result.success:
            self.log.warning("Failed to disassemble binary")
            return []
        
        violations = []
        current_symbol = None
        
        for line in result.stdout.split("\n"):
            # Track current symbol
            if line.endswith(">:"):
                match = re.search(r"<(.+)>:", line)
                if match:
                    current_symbol = match.group(1)
            
            # Check for SSE
            if self._sse_regex.search(line):
                match = re.match(r"\s*([0-9a-f]+):", line, re.IGNORECASE)
                if match:
                    addr = int(match.group(1), 16)
                    violations.append(SseViolation(
                        address=addr,
                        instruction=line.strip(),
                        symbol=current_symbol,
                    ))
        
        if violations:
            self.log.warning(f"⚠️ Found {len(violations)} SSE/AVX instructions!")
        else:
            self.log.success("No SSE/AVX instructions found")
        
        return violations
    
    async def get_sections(self, binary: Path) -> list[Section]:
        """List binary sections."""
        wsl_path = Paths.to_wsl(binary)
        cmd = f"objdump -h '{wsl_path}'"
        
        result = await self.wsl.run(cmd)
        
        if not result.success:
            return []
        
        sections = []
        
        for line in result.stdout.split("\n"):
            # Format: idx name size vma lma ...
            match = re.match(
                r"\s*\d+\s+(\S+)\s+([0-9a-f]+)\s+([0-9a-f]+)",
                line,
                re.IGNORECASE,
            )
            if match:
                name = match.group(1)
                size = int(match.group(2), 16)
                addr = int(match.group(3), 16)
                
                if size > 0:
                    sections.append(Section(
                        name=name,
                        address=addr,
                        size=size,
                    ))
        
        return sections
    
    async def get_entry_point(self, binary: Path) -> Optional[int]:
        """Get binary entry point."""
        wsl_path = Paths.to_wsl(binary)
        cmd = f"readelf -h '{wsl_path}' | grep 'Entry point'"
        
        result = await self.wsl.run(cmd)
        
        if result.success:
            match = re.search(r"0x([0-9a-f]+)", result.stdout, re.IGNORECASE)
            if match:
                return int(match.group(1), 16)
        
        return None

