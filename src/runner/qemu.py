"""
Anvil Runner - Configuração e lançamento do QEMU
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.config import AnvilConfig
from core.logger import log
from core.paths import PathResolver


@dataclass  
class QemuConfig:
    """Configuração específica de execução QEMU."""
    memory: str = "512M"
    serial: str = "stdio"
    monitor: str = "none"
    vga_memory: int = 16
    debug_flags: list[str] = field(default_factory=list)
    extra_args: list[str] = field(default_factory=list)
    enable_gdb: bool = False
    gdb_port: int = 1234


@dataclass
class QemuResult:
    """Resultado da execução QEMU."""
    exit_code: int
    runtime_ms: int
    crashed: bool = False
    crash_reason: Optional[str] = None


class QemuRunner:
    """Gerenciador de execução QEMU."""
    
    def __init__(self, paths: PathResolver, config: AnvilConfig):
        self.paths = paths
        self.config = config
        self.process: Optional[asyncio.subprocess.Process] = None
    
    def build_command(self, qemu_config: Optional[QemuConfig] = None) -> str:
        """
        Constrói comando QEMU para execução no WSL.
        """
        cfg = qemu_config or QemuConfig()
        
        # Caminhos WSL
        dist_path = PathResolver.windows_to_wsl(self.paths.dist_qemu)
        internal_log = PathResolver.windows_to_wsl(self.paths.internal_log)
        serial_log = PathResolver.windows_to_wsl(self.paths.serial_log)
        
        # Comando base
        cmd_parts = [
            "qemu-system-x86_64",
            f"-m {cfg.memory}",
            f"-drive file=fat:rw:'{dist_path}',format=raw",
            "-bios /usr/share/qemu/OVMF.fd",
            f"-serial {cfg.serial}",
            f"-monitor {cfg.monitor}",
            f"-device VGA,vgamem_mb={cfg.vga_memory}",
            "-no-reboot",
            "-no-shutdown",
        ]
        
        # Debug flags
        debug_flags = cfg.debug_flags or self.config.qemu.logging.flags
        if debug_flags:
            cmd_parts.append(f"-d {','.join(debug_flags)}")
        
        # Log file
        cmd_parts.append(f"-D '{internal_log}'")
        
        # Tee para log serial
        cmd_parts.append(f"2>&1 | tee '{serial_log}'")
        
        # GDB
        if cfg.enable_gdb:
            cmd_parts.append(f"-s -S")  # -s = gdb on :1234, -S = pause on start
        
        # Args extras
        for arg in cfg.extra_args:
            cmd_parts.append(arg)
        
        return " ".join(cmd_parts)
    
    async def run(self, qemu_config: Optional[QemuConfig] = None) -> asyncio.subprocess.Process:
        """
        Inicia QEMU via WSL e retorna o processo.
        """
        log.info("🚀 Iniciando QEMU via WSL...")
        
        cmd = self.build_command(qemu_config)
        log.step(f"Comando: {cmd[:80]}...")
        
        # Garantir que log existe e está vazio
        self.paths.internal_log.parent.mkdir(parents=True, exist_ok=True)
        self.paths.internal_log.write_text("")
        self.paths.serial_log.write_text("")
        
        self.process = await asyncio.create_subprocess_exec(
            "wsl", "bash", "-c", f"cd /tmp && {cmd}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        log.success(f"QEMU iniciado (PID: {self.process.pid})")
        return self.process
    
    async def stop(self) -> None:
        """Para execução do QEMU."""
        if self.process:
            log.info("⏹️ Parando QEMU...")
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
            self.process = None
    
    async def wait(self, timeout: Optional[float] = None) -> int:
        """Aguarda QEMU terminar."""
        if not self.process:
            return -1
        
        try:
            if timeout:
                return await asyncio.wait_for(
                    self.process.wait(),
                    timeout=timeout,
                )
            else:
                return await self.process.wait()
        except asyncio.TimeoutError:
            return -1
