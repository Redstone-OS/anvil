"""Anvil Runner - QEMU configuration and launcher."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from core.config import Config, QemuConfig
from core.paths import Paths
from core.logger import Logger, get_logger


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

    def build_command(self, override_config: Optional[QemuConfig] = None) -> str:
        """Build the QEMU command line for WSL."""
        cfg = override_config or self.config.qemu
        
        dist_path = Paths.to_wsl(self.paths.dist_qemu)
        internal_log = Paths.to_wsl(self.paths.cpu_log)
        serial_log = Paths.to_wsl(self.paths.serial_log)
        
        # Resolve OVMF path (if relative, it's relative to project root)
        ovmf_path = cfg.ovmf
        if not ovmf_path.startswith("/"):
            ovmf_path = Paths.to_wsl(self.config.project_root / ovmf_path)

        # Base command with memory and bios
        cmd_parts = [
            "qemu-system-x86_64",
            f"-m {cfg.memory}",
            f"-drive if={cfg.drive_interface},file=fat:rw:'{dist_path}',format=raw",
            f"-bios '{ovmf_path}'",
            f"-serial {cfg.serial}",
            f"-monitor {cfg.monitor}",
        ]
        
        # Logging flags
        flags = cfg.debug_flags or cfg.logging.flags
        if flags:
            cmd_parts.append(f"-d {','.join(flags)}")
        
        # Log file interno (CPU)
        cmd_parts.append(f"-D '{internal_log}'")
        
        # GDB
        if cfg.enable_gdb:
            cmd_parts.append(f"-s -S -p {cfg.gdb_port}")
        
        # Args extras (including those in anvil.toml like VGA, no-reboot, etc)
        extra = cfg.extra_args
        
        # SAFETY FALLBACK: If for some reason extra_args is empty or missing virtio, force it
        if not any("virtio-gpu" in str(a) for a in extra):
            if "-device" not in extra:
                extra.extend(["-device", "virtio-gpu-pci"])
        
        for arg in extra:
            if arg not in cmd_parts:
                cmd_parts.append(arg)
        
        # Final redirect for serial log
        # Note: tee must be the LAST part of the constructed shell string
        full_cmd = " ".join(cmd_parts)
        full_cmd += f" 2>&1 | tee '{serial_log}'"
        
        return full_cmd
    
    async def start(
        self,
        override_config: Optional[QemuConfig] = None,
    ) -> asyncio.subprocess.Process:
        """Start QEMU via WSL."""
        self.log.info("🚀 Iniciando QEMU via WSL...")
        
        cmd = self.build_command(override_config)
        self.log.info(f"Comando QEMU: {cmd}")
        
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
