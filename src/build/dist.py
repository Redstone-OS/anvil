"""Anvil Build - Distribution directory preparation."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from core.config import Config
from core.paths import Paths
from core.errors import BuildError
from core.logger import Logger, get_logger


class DistBuilder:
    """
    Prepares the dist/qemu directory for QEMU execution.
    
    Creates UEFI boot structure:
    dist/qemu/
    ├── EFI/BOOT/
    │   ├── BOOTX64.EFI    (bootloader)
    └── system/
        └── services/      (userspace services)
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
    
    def prepare(self, profile: str = "release") -> bool:
        """
        Complete distribution preparation.
        
        NOTE: This does NOT delete existing files. It only creates/overwrites
        artifacts, preserving any user data in the dist/qemu directory.
        
        Returns:
            True if successful
        
        Raises:
            BuildError: If required artifacts are missing
        """
        self.log.header("Preparing Distribution")
        
        self._create_structure()
        
        if not self._copy_bootloader(profile):
            raise BuildError("Bootloader is required", "dist")
        
        if not self._copy_kernel(profile):
            raise BuildError("Kernel is required", "dist")
        
        self._create_ignite_cfg()
        self._create_startup_nsh()
        
        self.log.success(f"dist/qemu ready: {self.paths.dist_qemu}")
        return True
    
    def _create_structure(self) -> None:
        """Create directory structure (without deleting existing files)."""
        self.log.info("📦 Creating distribution structure...")
        
        (self.paths.dist_qemu / "EFI" / "BOOT").mkdir(parents=True, exist_ok=True)
        (self.paths.dist_qemu / "boot").mkdir(parents=True, exist_ok=True)
        (self.paths.dist_qemu / "system" / "services").mkdir(parents=True, exist_ok=True)
        
        self.log.step("Structure: EFI/BOOT, boot, system/services")
    
    def _copy_bootloader(self, profile: str) -> bool:
        """Copy bootloader to EFI/BOOT/BOOTX64.EFI."""
        source = self.paths.bootloader_binary(profile)
        dest = self.paths.dist_qemu / "EFI" / "BOOT" / "BOOTX64.EFI"
        
        if not source.exists():
            self.log.error(f"Bootloader not found: {source}")
            return False
        
        shutil.copy2(source, dest)
        self.log.step(f"Bootloader → EFI/BOOT/BOOTX64.EFI ({source.stat().st_size:,} bytes)")
        return True
    
    def _copy_kernel(self, profile: str) -> bool:
        """Copy kernel to boot/kernel."""
        source = self.paths.kernel_binary(profile)
        dest = self.paths.dist_qemu / "boot" / "kernel"
        
        if not source.exists():
            self.log.error(f"Kernel not found: {source}")
            return False
        
        shutil.copy2(source, dest)
        self.log.step(f"Kernel → boot/kernel ({source.stat().st_size:,} bytes)")
        return True
    
    def _create_ignite_cfg(self) -> None:
        """Create the bootloader configuration file in EFI/BOOT/."""
        cfg_content = """timeout: 10
default_entry: 1
serial: true
quiet: false

# Default Entry
/Redstone OS
    protocol: redstone
    kernel_path: boot():/boot/kernel
    cmdline: verbose
    module_path: boot():/boot/initfs
"""
        dest = self.paths.dist_qemu / "EFI" / "BOOT" / "ignite.cfg"
        dest.write_text(cfg_content, encoding="utf-8")
        self.log.step("ignite.cfg criado em EFI/BOOT")
    
    def _create_startup_nsh(self) -> None:
        """Create UEFI Shell startup script for automatic boot."""
        # Script que faz boot automático quando o UEFI Shell inicia
        nsh_content = """@echo -off
FS0:
\\EFI\\BOOT\\BOOTX64.EFI
"""
        dest = self.paths.dist_qemu / "startup.nsh"
        dest.write_text(nsh_content, encoding="utf-8")
        self.log.step("startup.nsh criado para boot automático")
    
    def clean(self) -> None:
        """Ensure distribution directory exists without wiping it (following anvil_old)."""
        self.paths.dist_qemu.mkdir(parents=True, exist_ok=True)
        self.log.step("dist/qemu preservado (NVRAM mantida)")
