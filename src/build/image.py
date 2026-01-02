"""Anvil Build - Disk image creation (VDI)."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional

from core.config import Config
from core.paths import Paths
from core.errors import BuildError
from core.logger import Logger, get_logger


class ImageBuilder:
    """
    Disk image builder for VirtualBox.
    
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
        
        Saves to D:\\Github\\RedstoneOS\\dist\\img\\redstone(timestamp).vdi
        """
        self.log.header("Gerando Imagem VDI (VirtualBox)")
        
        # Ensure output directory exists: D:\Github\RedstoneOS\dist\img
        img_dir = self.paths.root / "dist" / "img"
        img_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        vdi_name = f"redstone_{timestamp}.vdi"
        vdi_path = img_dir / vdi_name
        raw_path = img_dir / f"redstone_{timestamp}.raw"
        
        self.log.info(f"Saída: {vdi_path}")
        
        try:
            # 1. Create RAW image via WSL
            if not await self._create_raw(raw_path):
                raise BuildError("Falha ao criar imagem RAW no WSL", "image")
            
            # 2. Convert RAW to VDI via WSL/QEMU
            if not await self._convert_to_vdi(raw_path, vdi_path):
                raise BuildError("Falha na conversão para VDI", "image")
            
            # Cleanup RAW
            if raw_path.exists():
                raw_path.unlink()
                
            self.log.success(f"VDI gerada com sucesso: {vdi_name}")
            return vdi_path
            
        except Exception as e:
            if raw_path.exists(): raw_path.unlink()
            self.log.error(f"Erro na geração da imagem: {e}")
            raise
    
    async def _run_wsl_logged(self, command: str) -> bool:
        """Run a WSL command and log its output in real-time."""
        self.log.info(f"Executando no WSL: {command[:80]}...")
        
        try:
            process = await asyncio.create_subprocess_exec(
                "wsl", "bash", "-c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                decoded = line.decode("utf-8", errors="replace").rstrip()
                if decoded:
                    # Log as step to keep it slightly muted but visible
                    self.log.step(decoded)
            
            await process.wait()
            return process.returncode == 0
            
        except Exception as e:
            self.log.error(f"Erro ao executar WSL: {e}")
            return False

    async def _create_raw(self, output: Path) -> bool:
        """Create and format RAW image using tools inside WSL."""
        img_size_mb = 128 # Increased to be safe
        
        wsl_output = Paths.to_wsl(output)
        # Use dist/qemu as the source of files
        wsl_dist = Paths.to_wsl(self.paths.dist_qemu)
        
        # 1. dd to create file
        # 2. mkfs.vfat to format
        # 3. mcopy to copy all files recursively
        cmd = (
            f"dd if=/dev/zero of='{wsl_output}' bs=1M count={img_size_mb} && "
            f"mkfs.vfat -F 32 '{wsl_output}' && "
            f"mcopy -i '{wsl_output}' -s '{wsl_dist}'/* ::/"
        )
        
        return await self._run_wsl_logged(cmd)

    async def _convert_to_vdi(self, source: Path, dest: Path) -> bool:
        """Convert RAW to VDI using qemu-img inside WSL."""
        wsl_src = Paths.to_wsl(source)
        wsl_dst = Paths.to_wsl(dest)
        
        cmd = f"qemu-img convert -f raw -O vdi '{wsl_src}' '{wsl_dst}'"
        return await self._run_wsl_logged(cmd)
