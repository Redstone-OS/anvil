"""
Anvil Runner - Executor WSL
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.logger import log
from core.paths import PathResolver


@dataclass
class WslResult:
    """Resultado de execução WSL."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str


class WslExecutor:
    """Executor de comandos via WSL."""
    
    def __init__(self):
        self._available: Optional[bool] = None
    
    async def is_available(self) -> bool:
        """Verifica se WSL está disponível."""
        if self._available is not None:
            return self._available
        
        try:
            process = await asyncio.create_subprocess_exec(
                "wsl", "--status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            self._available = process.returncode == 0
        except FileNotFoundError:
            self._available = False
        
        return self._available
    
    async def run(self, command: str, cwd: Optional[str] = None) -> WslResult:
        """
        Executa comando no WSL.
        
        Args:
            command: Comando bash a executar
            cwd: Diretório de trabalho (caminho WSL)
        """
        full_cmd = command
        if cwd:
            full_cmd = f"cd '{cwd}' && {command}"
        
        try:
            process = await asyncio.create_subprocess_exec(
                "wsl", "bash", "-c", full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            return WslResult(
                success=process.returncode == 0,
                exit_code=process.returncode or 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
            )
            
        except FileNotFoundError:
            return WslResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="WSL não disponível",
            )
    
    async def run_interactive(
        self,
        command: str,
        cwd: Optional[str] = None,
    ) -> asyncio.subprocess.Process:
        """
        Inicia processo interativo no WSL.
        
        Retorna o processo para monitoramento.
        """
        full_cmd = command
        if cwd:
            full_cmd = f"cd '{cwd}' && {command}"
        
        process = await asyncio.create_subprocess_exec(
            "wsl", "bash", "-c", full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        return process
    
    async def check_tool(self, tool: str) -> bool:
        """Verifica se ferramenta está instalada no WSL."""
        result = await self.run(f"which {tool}")
        return result.success
    
    async def check_required_tools(self) -> dict[str, bool]:
        """Verifica ferramentas necessárias."""
        tools = ["qemu-system-x86_64", "objdump", "nm", "addr2line", "tar"]
        result = {}
        
        for tool in tools:
            result[tool] = await self.check_tool(tool)
        
        return result
