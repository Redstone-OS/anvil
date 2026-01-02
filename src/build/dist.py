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
    Prepares the dist/ssd directory for QEMU execution.
    
    Creates simulated SSD structure with partitions:
    
    dist/ssd/
    ├── EFI/                    # Partition 1: ESP (FAT32)
    │   └── BOOT/
    │       ├── BOOTX64.EFI     (bootloader)
    │       └── ignite.cfg      (bootloader config)
    │
    └── RFS/                    # Partition 2: System (RFS/FAT32)
        ├── boot/
        │   ├── kernel          (kernel binary)
        │   └── initfs          (initramfs tar)
        └── system/
            └── services/       (compositor, shell, etc.)
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
        artifacts, preserving any user data in the dist/ssd directory.
        
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
        
        self._copy_ignite_cfg()
        self._copy_assets()
        
        self.log.success(f"dist/ssd ready: {self.paths.dist_ssd}")
        return True
    
    def _create_structure(self) -> None:
        """Create partition directory structure (without deleting existing files)."""
        self.log.info("📦 Creating distribution structure...")
        
        # EFI partition structure
        efi_boot = self.paths.dist_ssd_efi / "BOOT"
        efi_boot.mkdir(parents=True, exist_ok=True)
        
        # RFS partition structure  
        rfs_boot = self.paths.dist_ssd_rfs / "boot"
        rfs_system = self.paths.dist_ssd_rfs / "system" / "services"
        rfs_boot.mkdir(parents=True, exist_ok=True)
        rfs_system.mkdir(parents=True, exist_ok=True)
        
        self.log.step("Structure: EFI/BOOT, RFS/boot, RFS/system/services")
    
    def _copy_bootloader(self, profile: str) -> bool:
        """Copy bootloader to EFI/BOOT/BOOTX64.EFI."""
        source = self.paths.bootloader_binary(profile)
        dest = self.paths.dist_ssd_efi / "BOOT" / "BOOTX64.EFI"
        
        if not source.exists():
            self.log.error(f"Bootloader not found: {source}")
            return False
        
        shutil.copy2(source, dest)
        self.log.step(f"Bootloader → EFI/BOOT/BOOTX64.EFI ({source.stat().st_size:,} bytes)")
        return True
    
    def _copy_kernel(self, profile: str) -> bool:
        """Copy kernel to RFS/boot/kernel."""
        source = self.paths.kernel_binary(profile)
        dest = self.paths.dist_ssd_rfs / "boot" / "kernel"
        
        if not source.exists():
            self.log.error(f"Kernel not found: {source}")
            return False
        
        shutil.copy2(source, dest)
        self.log.step(f"Kernel → RFS/boot/kernel ({source.stat().st_size:,} bytes)")
        return True
    
    def _copy_ignite_cfg(self) -> None:
        """Create the bootloader configuration file in EFI/BOOT/."""
        cfg_content = """timeout: 10
default_entry: 1
serial: true
quiet: false

# Default Entry
/Redstone OS
    protocol: redstone
    kernel_path: \\RFS\\boot\\kernel
    cmdline: verbose
    module_path: \\RFS\\boot\\initfs

# Recovery Entry
/UEFI Shell (Recovery)
    protocol: chainload
    kernel_path: \\EFI\\BOOT\\shellx64.efi
"""
        dest = self.paths.dist_ssd_efi / "BOOT" / "ignite.cfg"
        dest.write_text(cfg_content, encoding="utf-8")
        self.log.step("ignite.cfg → EFI/BOOT/ignite.cfg")
    
    def _copy_assets(self) -> None:
        """Copy additional boot assets."""
        # UEFI Shell (optional)
        shell_source = self.paths.assets / "shellx64.efi"
        if shell_source.exists():
            dest = self.paths.dist_ssd_efi / "BOOT" / "shellx64.efi"
            shutil.copy2(shell_source, dest)
            self.log.step("UEFI Shell copied")
    
    def clean(self) -> None:
        """Clean entire dist directory (use with caution)."""
        if self.paths.dist.exists():
            shutil.rmtree(self.paths.dist)
            self.log.step("Cleaned dist/")
    
    def clean_artifacts_only(self) -> None:
        """Clean only build artifacts, preserving user data."""
        artifacts = [
            self.paths.dist_ssd_efi / "BOOT" / "BOOTX64.EFI",
            self.paths.dist_ssd_efi / "BOOT" / "ignite.cfg",
            self.paths.dist_ssd_efi / "BOOT" / "shellx64.efi",
            self.paths.dist_ssd_rfs / "boot" / "kernel",
            self.paths.dist_ssd_rfs / "boot" / "initfs",
        ]
        for artifact in artifacts:
            if artifact.exists():
                artifact.unlink()
        self.log.step("Cleaned build artifacts only")
