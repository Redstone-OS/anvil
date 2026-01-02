"""Anvil Build - Disk image creation (VDI)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from core.config import Config
from core.paths import Paths
from core.errors import BuildError
from core.logger import Logger, get_logger


class ImageBuilder:
    """
    Disk image builder for VirtualBox/VMware.
    
    Creates:
    1. RAW image with FAT32 filesystem (via WSL)
    2. Converts to VDI format (via qemu-img)
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
    
    async def build_vdi(self, profile: str = "release") -> Path:
        """
        Build a VDI disk image.
        
        1. Create FAT32 RAW image via WSL
        2. Convert to VDI via qemu-img
        
        Returns:
            Path to the created VDI file
        
        Raises:
            BuildError: If image creation fails
        """
        self.log.header("Creating VDI Image")
        
        self.paths.ensure_dirs()
        
        raw_path = self.paths.dist_img / "redstone.raw"
        vdi_path = self.paths.dist_img / "redstone.vdi"
        
        # Create RAW image
        if not await self._create_raw(raw_path, profile):
            raise BuildError("Failed to create RAW image", "image")
        
        # Convert to VDI
        if not await self._convert_to_vdi(raw_path, vdi_path):
            raw_path.unlink(missing_ok=True)
            raise BuildError("Failed to convert to VDI", "image")
        
        # Clean up RAW
        raw_path.unlink(missing_ok=True)
        
        self.log.success(f"VDI created: {self.paths.relative(vdi_path)}")
        return vdi_path
    
    async def _create_raw(self, output: Path, profile: str) -> bool:
        """Create FAT32-formatted RAW image with dist/qemu contents."""
        self.log.info(f"📂 Creating RAW image ({output.name})...")
        
        img_size_mb = 64  # TODO: Calculate dynamically
        
        wsl_output = Paths.to_wsl(output)
        wsl_dist = Paths.to_wsl(self.paths.dist_qemu)
        
        # WSL commands:
        # 1. Create empty file
        # 2. Format as FAT32
        # 3. Copy contents with mcopy
        commands = [
            f"dd if=/dev/zero of='{wsl_output}' bs=1M count={img_size_mb}",
            f"mkfs.vfat -F 32 '{wsl_output}'",
            f"mcopy -i '{wsl_output}' -s '{wsl_dist}'/* ::/",
        ]
        
        full_cmd = " && ".join(commands)
        
        try:
            process = await asyncio.create_subprocess_exec(
                "wsl", "bash", "-c", full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                self.log.error(f"WSL error: {stderr.decode()}")
                return False
            
            self.log.step(f"RAW {img_size_mb}MB formatted and populated")
            return True
        
        except Exception as e:
            self.log.error(f"Exception creating RAW: {e}")
            return False
    
    async def _convert_to_vdi(self, source: Path, dest: Path) -> bool:
        """Convert RAW image to VDI using qemu-img."""
        self.log.info(f"💾 Converting to VDI ({dest.name})...")
        
        # Try WSL first
        wsl_src = Paths.to_wsl(source)
        wsl_dst = Paths.to_wsl(dest)
        
        cmd = f"qemu-img convert -f raw -O vdi '{wsl_src}' '{wsl_dst}'"
        
        try:
            process = await asyncio.create_subprocess_exec(
                "wsl", "bash", "-c", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                # Fallback: try Windows qemu-img
                self.log.warning("WSL conversion failed, trying Windows...")
                return await self._convert_windows(source, dest)
            
            self.log.step(f"Conversion complete: {dest.stat().st_size:,} bytes")
            return True
        
        except Exception as e:
            self.log.error(f"Exception converting: {e}")
            return False
    
    async def _convert_windows(self, source: Path, dest: Path) -> bool:
        """Fallback: Convert using Windows qemu-img."""
        try:
            process = await asyncio.create_subprocess_exec(
                "qemu-img", "convert",
                "-f", "raw",
                "-O", "vdi",
                str(source),
                str(dest),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                self.log.error(f"Windows conversion failed: {stderr.decode()}")
                return False
            
            return True
        
        except FileNotFoundError:
            self.log.error("qemu-img not found on Windows")
            return False

