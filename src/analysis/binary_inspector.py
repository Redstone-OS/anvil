"""
Anvil Analysis - Inspetor de binários
"""

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.logger import log
from runner.wsl import WslExecutor
from core.paths import PathResolver


@dataclass
class Symbol:
    """Símbolo encontrado no binário."""
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
    """Seção do binário."""
    name: str
    address: int
    size: int
    flags: str = ""


@dataclass
class Disassembly:
    """Resultado de disassembly."""
    address: int
    instructions: list[tuple[int, str, str]]  # (addr, bytes, asm)
    symbol: Optional[Symbol] = None


@dataclass
class SseViolation:
    """Violação de uso de SSE no kernel."""
    address: int
    instruction: str
    context: str = ""
    symbol: Optional[str] = None


class BinaryInspector:
    """
    Inspetor de binários para diagnóstico.
    
    Usa ferramentas do WSL (objdump, nm, addr2line) para:
    - Desmontar código em endereço específico
    - Encontrar símbolos
    - Detectar instruções SSE proibidas
    """
    
    # Instruções SSE/AVX a detectar
    SSE_PATTERNS = [
        r"\b(movaps|movups|movss|movsd)\b",
        r"\b(addps|addss|subps|subss|mulps|mulss|divps|divss)\b",
        r"\b(xmm[0-9]+|ymm[0-9]+|zmm[0-9]+)\b",
        r"\b(vmov|vadd|vsub|vmul|vdiv)\w*\b",
        r"\b(pxor|movdqa|movdqu|paddd|psubd)\b",
    ]
    
    def __init__(self, paths: PathResolver):
        self.paths = paths
        self.wsl = WslExecutor()
        self._sse_regex = re.compile("|".join(self.SSE_PATTERNS), re.IGNORECASE)
    
    async def disassemble_at(
        self,
        binary: Path,
        address: int,
        context: int = 20,
    ) -> Optional[Disassembly]:
        """
        Desmonta código no endereço especificado.
        
        Args:
            binary: Caminho do binário
            address: Endereço para desmontar
            context: Número de instruções de contexto
        """
        wsl_path = PathResolver.windows_to_wsl(binary)
        
        # Calcular range
        start_addr = max(0, address - context * 4)  # Média de 4 bytes por instrução
        end_addr = address + context * 4
        
        cmd = (
            f"objdump -d --no-show-raw-insn "
            f"--start-address=0x{start_addr:x} "
            f"--stop-address=0x{end_addr:x} "
            f"'{wsl_path}'"
        )
        
        result = await self.wsl.run(cmd)
        
        if not result.success:
            log.warning(f"objdump falhou: {result.stderr}")
            return None
        
        # Parsear output
        instructions = []
        current_symbol = None
        
        for line in result.stdout.split("\n"):
            # Detectar símbolo
            if line.endswith(">:"):
                sym_match = re.search(r"<(.+)>:", line)
                if sym_match:
                    current_symbol = sym_match.group(1)
            
            # Parsear instrução
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
    
    async def find_symbol_at(self, binary: Path, address: int) -> Optional[Symbol]:
        """
        Encontra símbolo no endereço usando addr2line e nm.
        """
        wsl_path = PathResolver.windows_to_wsl(binary)
        
        # Tentar addr2line primeiro (com -C para demangle, -f para function name)
        cmd = f"addr2line -C -f -e '{wsl_path}' 0x{address:x}"
        result = await self.wsl.run(cmd)
        
        if result.success and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            # Output esperado:
            # FunctionName
            # /path/to/file.rs:123
            
            if len(lines) >= 2:
                func_name = lines[0]
                file_info = lines[1]
                
                if func_name != "??" and func_name != "":
                    file_path: Optional[str] = None
                    line_num: Optional[int] = None
                    
                    if ":" in file_info:
                        # Extrair path e linha
                        # Cuidado com paths Windows que podem ter C:\... mas addr2line roda no WSL
                        # Normalmente output é unix style ou relative
                        parts = file_info.rsplit(":", 1)
                        if len(parts) == 2 and parts[1].isdigit():
                            file_path = parts[0]
                            line_num = int(parts[1])
                        else:
                            file_path = file_info
                    
                    return Symbol(
                        name=func_name,
                        address=address,
                        file=file_path,
                        line=line_num,
                    )
        
        # Fallback: nm e busca manual
        cmd = f"nm -C '{wsl_path}' | sort -k1"
        result = await self.wsl.run(cmd)
        
        if not result.success:
            return None
        
        # Encontrar símbolo mais próximo
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
    
    async def check_sse_instructions(self, binary: Path) -> list[SseViolation]:
        """
        Escaneia binário por instruções SSE/AVX proibidas.
        """
        log.info(f"🔍 Escaneando {binary.name} por instruções SSE/AVX...")
        
        wsl_path = PathResolver.windows_to_wsl(binary)
        cmd = f"objdump -d '{wsl_path}'"
        
        result = await self.wsl.run(cmd)
        
        if not result.success:
            log.warning("Falha ao desmontar binário")
            return []
        
        violations = []
        current_symbol = None
        
        for line in result.stdout.split("\n"):
            # Detectar símbolo
            if line.endswith(">:"):
                sym_match = re.search(r"<(.+)>:", line)
                if sym_match:
                    current_symbol = sym_match.group(1)
            
            # Verificar SSE
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
            log.warning(f"⚠️ Encontradas {len(violations)} instruções SSE/AVX!")
        else:
            log.success("Nenhuma instrução SSE/AVX encontrada")
        
        return violations
    
    async def analyze_sections(self, binary: Path) -> list[Section]:
        """Lista seções do binário com tamanhos e permissões."""
        wsl_path = PathResolver.windows_to_wsl(binary)
        cmd = f"objdump -h '{wsl_path}'"
        
        result = await self.wsl.run(cmd)
        
        if not result.success:
            return []
        
        sections = []
        
        # Parsear output do objdump -h
        for line in result.stdout.split("\n"):
            # Formato: idx name size vma lma ...
            match = re.match(
                r"\s*\d+\s+(\S+)\s+([0-9a-f]+)\s+([0-9a-f]+)",
                line,
                re.IGNORECASE,
            )
            if match:
                name = match.group(1)
                size = int(match.group(2), 16)
                addr = int(match.group(3), 16)
                
                if size > 0:  # Ignorar seções vazias
                    sections.append(Section(
                        name=name,
                        address=addr,
                        size=size,
                    ))
        
        return sections
    
    async def get_entry_point(self, binary: Path) -> Optional[int]:
        """Obtém entry point do binário."""
        wsl_path = PathResolver.windows_to_wsl(binary)
        cmd = f"readelf -h '{wsl_path}' | grep 'Entry point'"
        
        result = await self.wsl.run(cmd)
        
        if result.success:
            match = re.search(r"0x([0-9a-f]+)", result.stdout, re.IGNORECASE)
            if match:
                return int(match.group(1), 16)
        
        return None
