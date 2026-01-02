"""Anvil Runner - WSL command executor."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional


@dataclass
class WslResult:
    """Result of a WSL command execution."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str


class WslExecutor:
    """
    Command executor for Windows Subsystem for Linux.
    
    Provides async execution of bash commands in WSL.
    """
    
    def __init__(self):
        self._available: Optional[bool] = None
    
    async def is_available(self) -> bool:
        """Check if WSL is available."""
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
    
    async def run(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> WslResult:
        """
        Execute a bash command in WSL.
        
        Args:
            command: Bash command to execute
            cwd: Working directory (WSL path format)
            timeout: Optional timeout in seconds
        
        Returns:
            WslResult with stdout, stderr, and exit code
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
            
            if timeout:
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    return WslResult(
                        success=False,
                        exit_code=-1,
                        stdout="",
                        stderr="Command timed out",
                    )
            else:
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
                stderr="WSL not available",
            )
    
    async def run_interactive(
        self,
        command: str,
        cwd: Optional[str] = None,
    ) -> asyncio.subprocess.Process:
        """
        Start an interactive process in WSL.
        
        Returns the subprocess for streaming output.
        """
        full_cmd = command
        if cwd:
            full_cmd = f"cd '{cwd}' && {command}"
        
        return await asyncio.create_subprocess_exec(
            "wsl", "bash", "-c", full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    
    async def check_tool(self, tool: str) -> bool:
        """Check if a tool is available in WSL."""
        result = await self.run(f"which {tool}")
        return result.success
    
    async def check_required_tools(self) -> dict[str, bool]:
        """Check all tools required by Anvil."""
        tools = [
            "qemu-system-x86_64",
            "objdump",
            "nm",
            "addr2line",
            "tar",
            "mkfs.vfat",
            "mcopy",
        ]
        
        results = {}
        for tool in tools:
            results[tool] = await self.check_tool(tool)
        
        return results

