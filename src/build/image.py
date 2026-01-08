"""Anvil Build - Criação de Imagem de Disco."""

import asyncio
import time
from pathlib import Path
from typing import Optional

from core.config import Config
from core.paths import Paths
from core.errors import BuildError
from core.logger import Logger, get_logger

class ImageBuilder:
    """Ferramenta para criar imagens VDI (VirtualBox) a partir da pasta dist."""
    
    def __init__(self, paths: Paths, config: Config, log: Optional[Logger] = None):
        self.paths = paths
        self.config = config
        self.log = log or get_logger()
        
    async def build_vdi(self, profile: str = "release") -> Path:
        """Cria uma imagem .vdi contendo todo o diretório dist/qemu."""
        self.log.header("Gerando Imagem VDI (VirtualBox)")
        
        img_dir = self.paths.root / "dist" / "img"
        img_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        vdi_name = f"redstone_{timestamp}.vdi"
        vdi_path = img_dir / vdi_name
        raw_path = img_dir / f"redstone_{timestamp}.raw"
        
        self.log.info(f"Saída: {vdi_path}")
        
        try:
            # 1. Cria imagem FAT32 bruta (RAW)
            if not await self._create_raw(raw_path):
                raise BuildError("Falha ao criar imagem RAW no WSL", "image")
            
            # 2. Converte RAW para VDI
            if not await self._convert_to_vdi(raw_path, vdi_path):
                raise BuildError("Falha na conversão para VDI", "image")
            
            # Limpa temporário
            if raw_path.exists(): raw_path.unlink()
            
            self.log.success(f"VDI gerada: {vdi_name}")
            return vdi_path
            
        except Exception as e:
            if raw_path.exists(): raw_path.unlink()
            self.log.error(f"Erro na geração da imagem: {e}")
            raise
            
    async def _run_wsl_logged(self, command: str) -> bool:
        """Roda comando no WSL e loga a saída."""
        self.log.info(f"Executando no WSL: {command[:80]}...")
        try:
            p = await asyncio.create_subprocess_exec(
                "wsl", "bash", "-c", command,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            while True:
                line = await p.stdout.readline()
                if not line: break
                decoded = line.decode("utf-8", errors="replace").rstrip()
                if decoded: self.log.step(decoded)
            
            await p.wait()
            return p.returncode == 0
        except Exception as e:
            self.log.error(f"Erro WSL: {e}")
            return False
            
    async def _create_raw(self, output: Path) -> bool:
        """Cria e formata imagem raw usando ferramentas Linux."""
        img_size_mb = 128
        wsl_output = Paths.to_wsl(output)
        wsl_dist = Paths.to_wsl(self.paths.dist_qemu)
        
        # dd: cria arquivo vazio
        # mkfs.vfat: formata como FAT32
        # mcopy: copia arquivos para dentro da imagem FAT
        cmd = (
            f"dd if=/dev/zero of='{wsl_output}' bs=1M count={img_size_mb} && "
            f"mkfs.vfat -F 32 '{wsl_output}' && "
            f"mcopy -i '{wsl_output}' -s '{wsl_dist}'/* ::/"
        )
        return await self._run_wsl_logged(cmd)
        
    async def _convert_to_vdi(self, source: Path, dest: Path) -> bool:
        """Usa qemu-img para converter raw -> vdi."""
        wsl_src = Paths.to_wsl(source)
        wsl_dst = Paths.to_wsl(dest)
        cmd = f"qemu-img convert -f raw -O vdi '{wsl_src}' '{wsl_dst}'"
        return await self._run_wsl_logged(cmd)
