"""Anvil Runner - QEMU configuration and launcher."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from core.config import Config
from core.paths import Paths
from core.logger import Logger, get_logger


@dataclass
class QemuConfig:
    """QEMU execution configuration."""
    memory: str = "512M"
    serial: str = "stdio"
    monitor: str = "none"
    vga_memory: int = 16
    debug_flags: list[str] = field(default_factory=list)
    extra_args: list[str] = field(default_factory=list)
    enable_gdb: bool = False
    gdb_port: int = 1234


class QemuRunner:
    """
    QEMU process manager.
    
    Launches QEMU via WSL following the anvil_old pattern.
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
        self.process: Optional[asyncio.subprocess.Process] = None
    
    def build_command(self, qemu_config: Optional[QemuConfig] = None) -> str:
        """Build the QEMU command line for WSL."""
        cfg = qemu_config or QemuConfig()
        
        dist_path = Paths.to_wsl(self.paths.dist_qemu)
        internal_log = Paths.to_wsl(self.paths.cpu_log)
        serial_log = Paths.to_wsl(self.paths.serial_log)
        
        # Comando EXATAMENTE igual ao anvil_old
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
        
        # Log file interno (CPU)
        cmd_parts.append(f"-D '{internal_log}'")
        
        # Tee para log serial (redireciona stderr para stdout e grava no arquivo)
        cmd_parts.append(f"2>&1 | tee '{serial_log}'")
        
        # GDB
        if cfg.enable_gdb:
            cmd_parts.append("-s -S")
        
        # Args extras
        for arg in cfg.extra_args:
            cmd_parts.append(arg)
        
        return " ".join(cmd_parts)
    
    async def start(
        self,
        qemu_config: Optional[QemuConfig] = None,
    ) -> asyncio.subprocess.Process:
        """Start QEMU via WSL."""
        self.log.info("🚀 Iniciando QEMU via WSL...")
        
        cmd = self.build_command(qemu_config)
        self.log.step(f"Comando: {cmd[:80]}...")
        
        # Garantir logs limpos
        self.paths.cpu_log.parent.mkdir(parents=True, exist_ok=True)
        self.paths.cpu_log.write_text("")
        self.paths.serial_log.write_text("")
        
        # O cd /tmp && {cmd} do anvil_old ajuda na estabilidade
        self.process = await asyncio.create_subprocess_exec(
            "wsl", "bash", "-c", f"cd /tmp && {cmd}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        self.log.success(f"QEMU iniciado (PID: {self.process.pid})")
        return self.process
    
    async def stop(self) -> None:
        if self.process:
            self.log.info("⏹️ Parando QEMU...")
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
            self.process = None
