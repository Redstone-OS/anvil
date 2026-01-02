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
    memory: str = "4097M"
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
    
    Launches QEMU via WSL with dual-disk setup simulating SSD partitions:
    - Disk 0 (IDE): EFI partition with bootloader (for UEFI boot)
    - Disk 1 (VirtIO): RFS partition with system files
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
        
        # WSL paths for each partition
        efi_path = Paths.to_wsl(self.paths.dist_ssd_efi)
        rfs_path = Paths.to_wsl(self.paths.dist_ssd_rfs)
        internal_log = Paths.to_wsl(self.paths.cpu_log)
        serial_log = Paths.to_wsl(self.paths.serial_log)
        
        parts = [
            "qemu-system-x86_64",
            f"-m {cfg.memory}",
            # Disk 0: EFI partition (IDE for reliable UEFI boot)
            f"-drive file=fat:rw:'{efi_path}',format=raw",
            # Disk 1: RFS partition (VirtIO for performance)
            f"-drive file=fat:rw:'{rfs_path}',format=raw,if=virtio",
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
            parts.append(f"-d {','.join(debug_flags)}")
        
        # Log files
        parts.append(f"-D '{internal_log}'")
        
        # Tee serial to file
        parts.append(f"2>&1 | tee '{serial_log}'")
        
        # GDB server
        if cfg.enable_gdb:
            parts.append(f"-s -S")  # -s = gdb :1234, -S = pause on start
        
        # Extra args
        for arg in cfg.extra_args:
            parts.append(arg)
        
        return " ".join(parts)
    
    async def start(
        self,
        qemu_config: Optional[QemuConfig] = None,
    ) -> asyncio.subprocess.Process:
        """
        Start QEMU via WSL.
        
        Returns the subprocess for monitoring.
        """
        self.log.info("🚀 Starting QEMU via WSL...")
        
        cmd = self.build_command(qemu_config)
        self.log.step(f"Command: {cmd[:80]}...")
        
        # Ensure log files exist
        self.paths.cpu_log.parent.mkdir(parents=True, exist_ok=True)
        self.paths.cpu_log.write_text("")
        self.paths.serial_log.write_text("")
        
        self.process = await asyncio.create_subprocess_exec(
            "wsl", "bash", "-c", f"cd /tmp && {cmd}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        self.log.success(f"QEMU started (PID: {self.process.pid})")
        return self.process
    
    async def stop(self) -> None:
        """Stop QEMU process."""
        if self.process:
            self.log.info("⏹️ Stopping QEMU...")
            self.process.terminate()
            
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
            
            self.process = None
    
    async def wait(self, timeout: Optional[float] = None) -> int:
        """Wait for QEMU to exit."""
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
