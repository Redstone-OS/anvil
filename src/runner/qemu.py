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
    
    Launches QEMU via WSL with UEFI boot.
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
        
        # Estrutura base do comando
        parts = [
            "qemu-system-x86_64",
            f"-m {cfg.memory}",
            # Forçamos o disco a ser a primeira unidade de boot com index=0
            f"-drive file=fat:rw:'{dist_path}',format=raw,if=ide,index=0,media=disk",
            "-bios /usr/share/qemu/OVMF.fd",
            f"-serial {cfg.serial}",
            f"-monitor {cfg.monitor}",
            f"-device VGA,vgamem_mb={cfg.vga_memory}",
            "-no-reboot",
            "-no-shutdown",
            # Desativa o menu de boot interativo para forçar o carregamento direto
            "-boot menu=off",
        ]
        
        # Debug flags
        debug_flags = cfg.debug_flags or self.config.qemu.logging.flags
        if debug_flags:
            parts.append(f"-d {','.join(debug_flags)}")
        
        # Log files
        parts.append(f"-D '{internal_log}'")
        
        # GDB server
        if cfg.enable_gdb:
            parts.append(f"-s -S")
        
        # Extra args
        for arg in cfg.extra_args:
            parts.append(arg)
        
        # Monta o comando final. 
        # IMPORTANTE: Removido o 'tee' para evitar lentidão e problemas de sincronia no console.
        return " ".join(parts)
    
    async def start(
        self,
        qemu_config: Optional[QemuConfig] = None,
    ) -> asyncio.subprocess.Process:
        """Start QEMU via WSL."""
        self.log.info("🚀 Iniciando QEMU via WSL...")
        
        cmd = self.build_command(qemu_config)
        self.log.step(f"Comando: {cmd[:80]}...")
        
        # Ensure log files exist
        self.paths.cpu_log.parent.mkdir(parents=True, exist_ok=True)
        self.paths.cpu_log.write_text("")
        
        # Delay de 200ms para garantir que o sistema de arquivos do Windows/WSL está estável
        await asyncio.sleep(0.2)
        
        self.process = await asyncio.create_subprocess_exec(
            "wsl", "bash", "-c", cmd,
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
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self.process.kill()
            self.process = None
