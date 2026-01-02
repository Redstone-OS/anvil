"""Anvil Build - InitRAMFS creation and services deployment."""

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
    Builder for the kernel's InitRAMFS and services deployment.
    
    InitRAMFS (boot/initfs) - Minimal bootstrap:
    /system/
    └── core/
        └── supervisor   # PID 1 only!
    
    dist/qemu/system/services/ - Full services:
    ├── firefly
    └── shell
    """
    
    # Minimal initfs structure (just for supervisor)
    INITFS_DIRECTORIES = [
        "system/core",
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
        """Build the initramfs and deploy services."""
        self.log.header("Building InitRAMFS + Services")
        
        # Clean staging directory
        self._clean_staging()
        
        # Create minimal initfs structure
        self._create_initfs_structure()
        
        # Add ONLY supervisor to initfs
        supervisor_path = self.paths.service_binary("supervisor", profile)
        if not self._add_to_initfs("supervisor", supervisor_path):
            raise BuildError("Supervisor service is required", "initramfs")
        
        # Create initfs TAR
        output = self.paths.dist_qemu / "boot" / "initfs"
        output.parent.mkdir(parents=True, exist_ok=True)
        tar_size = await self._create_tar(output)
        
        if tar_size is None:
            return False
        
        # Deploy other services to dist/qemu/system/services/
        await self._deploy_services(profile)
        
        # Deploy apps to dist/qemu/apps/system/
        await self._deploy_apps(profile)
        
        # Create manifest
        self._create_manifest()
        
        return True
    
    def _clean_staging(self) -> None:
        """Clean the initramfs staging directory."""
        if self.paths.initramfs.exists():
            shutil.rmtree(self.paths.initramfs)
        self.paths.initramfs.mkdir(parents=True, exist_ok=True)
    
    def _create_initfs_structure(self) -> None:
        """Create minimal initfs directory structure (supervisor only)."""
        self.log.info("📂 Creating minimal initfs structure...")
        
        for dir_path in self.INITFS_DIRECTORIES:
            full_path = self.paths.initramfs / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
        
        self.log.step("Structure: /system/core (supervisor only)")
    
    def _add_to_initfs(self, name: str, source: Path) -> bool:
        """Add a binary to the initfs (only for supervisor)."""
        if not source.exists():
            self.log.error(f"Service '{name}' not found: {source}")
            return False
        
        dest = f"system/core/{name}"
        dest_path = self.paths.initramfs / dest
        shutil.copy2(source, dest_path)
        
        self.entries.append(InitramfsEntry(
            source=source,
            dest=dest,
            size=source.stat().st_size,
        ))
        
        self.log.step(f"initfs: /{dest} ({source.stat().st_size:,} bytes)")
        return True
    
    async def _deploy_services(self, profile: str) -> None:
        """Deploy all non-supervisor services to dist/qemu/system/services/."""
        self.log.info("📦 Deploying services...")
        
        services_dir = self.paths.dist_qemu / "system" / "services"
        services_dir.mkdir(parents=True, exist_ok=True)
        
        deployed = 0
        for svc in self.config.components.services:
            # Skip supervisor (it's in initfs)
            if svc.name == "supervisor":
                continue
            
            svc_path = self.paths.service_binary(
                svc.name,
                profile,
                base_path=self.paths.root / svc.path,
            )
            
            if not svc_path.exists():
                self.log.warning(f"Service '{svc.name}' not found: {svc_path}")
                continue
            
            dest = services_dir / svc.name
            shutil.copy2(svc_path, dest)
            deployed += 1
            
            self.log.step(f"/system/services/{svc.name} ({svc_path.stat().st_size:,} bytes)")
        
        self.log.success(f"Deployed {deployed} services")
    
    async def _deploy_apps(self, profile: str) -> None:
        """Deploy all apps to dist/qemu/apps/system/."""
        self.log.info("📦 Deploying apps...")
        
        apps_dir = self.paths.dist_qemu / "apps" / "system"
        apps_dir.mkdir(parents=True, exist_ok=True)
        
        deployed = 0
        for app in self.config.components.apps:
            app_path = self.paths.service_binary(
                app.name,
                profile,
                base_path=self.paths.root / app.path,
            )
            
            if not app_path.exists():
                self.log.warning(f"App '{app.name}' not found: {app_path}")
                continue
            
            dest = apps_dir / app.name
            shutil.copy2(app_path, dest)
            deployed += 1
            
            self.log.step(f"/apps/system/{app.name} ({app_path.stat().st_size:,} bytes)")
        
        self.log.success(f"Deployed {deployed} apps")
    
    def _create_manifest(self) -> None:
        """Create services manifest."""
        manifests_dir = self.paths.dist_qemu / "system" / "manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)
        
        manifest_path = manifests_dir / "services.toml"
        
        lines = [
            "# RedstoneOS Services Manifest",
            "# /system/manifests/services.toml",
            "",
        ]
        
        for svc in self.config.components.services:
            if svc.name == "supervisor":
                continue
            
            lines.extend([
                f"[[service]]",
                f'name = "{svc.name}"',
                f'path = "/system/services/{svc.name}"',
                f'restart = "always"',
                "",
            ])
        
        manifest_path.write_text("\n".join(lines), encoding="utf-8")
        self.log.step("/system/manifests/services.toml created")
    
    async def _create_tar(self, output: Path) -> Optional[int]:
        """Create TAR archive via WSL."""
        self.log.info("📦 Creating initfs archive (supervisor only)...")
        
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
