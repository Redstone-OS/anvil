"""Anvil Build - InitRAMFS creation."""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config import Config
from core.paths import Paths
from core.errors import BuildError
from core.logger import Logger, get_logger


@dataclass
class InitramfsEntry:
    """Entry in the initramfs."""
    source: Path
    dest: str  # Path inside initramfs
    size: int = 0


class InitramfsBuilder:
    """
    Builder for the kernel's InitRAMFS.
    
    Creates a TAR archive with the RedstoneOS userspace structure:
    
    /system/
    ├── core/       - Core services (PID 1, etc.)
    ├── services/   - User services (compositor, shell, etc.)
    ├── drivers/    - Userspace drivers
    └── manifests/  - Service configuration
    
    /runtime/
    ├── ipc/        - IPC endpoints
    └── logs/       - Runtime logs
    
    /state/
    ├── system/     - System state
    └── services/   - Per-service state
    """
    
    DIRECTORIES = [
        "system/core",
        "system/services",
        "system/drivers",
        "system/manifests",
        "runtime/ipc",
        "runtime/logs",
        "state/system",
        "state/services",
    ]
    
    def __init__(
        self,
        paths: Paths,
        config: Config,
        log: Optional[Logger] = None,
    ):
        self.paths = paths
        self.config = config
        self.log = log or get_logger()
        self.entries: list[InitramfsEntry] = []
    
    async def build(self, profile: str = "release") -> bool:
        """Build the complete initramfs."""
        self.log.header("Building InitRAMFS")
        
        self._create_structure()
        
        # Add supervisor (PID 1)
        supervisor_path = self.paths.service_binary("supervisor", profile)
        if not self._add_service("supervisor", supervisor_path, core=False):
            raise BuildError("Supervisor service is required", "initramfs")
        
        # Add all other services from config
        for svc in self.config.components.services:
            if svc.name == "supervisor":
                continue
            
            svc_path = self.paths.service_binary(
                svc.name,
                profile,
                base_path=self.paths.root / svc.path,
            )
            self._add_service(svc.name, svc_path, core=svc.core)
        
        # Create manifest
        self._create_manifest()
        
        # Create TAR via WSL
        output = self.paths.dist_qemu / "boot" / "initfs"
        output.parent.mkdir(parents=True, exist_ok=True)
        
        tar_size = await self._create_tar(output)
        return tar_size is not None
    
    def _create_structure(self) -> None:
        """Create directory structure."""
        self.log.info("📂 Creating initramfs structure...")
        
        for dir_path in self.DIRECTORIES:
            full_path = self.paths.initramfs / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
        
        self.log.step("Structure: /system, /runtime, /state created")
    
    def _add_service(
        self,
        name: str,
        source: Path,
        core: bool = False,
    ) -> bool:
        """Add a service binary to the initramfs."""
        if not source.exists():
            self.log.warning(f"Service '{name}' not found: {source}")
            return False
        
        dest_dir = "system/core" if core else "system/services"
        dest = f"{dest_dir}/{name}"
        
        dest_path = self.paths.initramfs / dest
        shutil.copy2(source, dest_path)
        
        self.entries.append(InitramfsEntry(
            source=source,
            dest=dest,
            size=source.stat().st_size,
        ))
        
        self.log.step(f"/{dest} ({source.stat().st_size:,} bytes)")
        return True
    
    def _create_manifest(self) -> None:
        """Create services manifest file."""
        manifest_path = self.paths.initramfs / "system/manifests/services.toml"
        
        content = """# RedstoneOS Services Manifest
# /system/manifests/services.toml

[init]
path = "/system/core/init"
restart = "never"
depends = []
"""
        
        manifest_path.write_text(content, encoding="utf-8")
        self.log.step("/system/manifests/services.toml created")
    
    async def _create_tar(self, output: Path) -> Optional[int]:
        """Create TAR archive via WSL."""
        self.log.info("📦 Creating initfs archive...")
        
        wsl_initramfs = Paths.to_wsl(self.paths.initramfs)
        wsl_output = Paths.to_wsl(output)
        
        cmd = f"tar -cf '{wsl_output}' -C '{wsl_initramfs}' ."
        
        try:
            process = await asyncio.create_subprocess_exec(
                "wsl", "bash", "-c", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                self.log.error(f"TAR creation failed: {stderr.decode()}")
                return None
            
            size = output.stat().st_size
            self.log.success(f"initfs created ({size / 1024:.2f} KB)")
            return size
        
        except FileNotFoundError:
            self.log.error("WSL not available")
            return None

