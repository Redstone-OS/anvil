"""
Anvil Build - Criação de imagens de disco (VDI)
"""

import asyncio
import shutil
from pathlib import Path
from typing import Optional

from core.config import AnvilConfig
from core.logger import log
from core.paths import PathResolver
from core.exceptions import BuildError


class ImageBuilder:
    """Builder de imagens de disco (RAW e VDI)."""
    
    def __init__(self, paths: PathResolver, config: AnvilConfig):
        self.paths = paths
        self.config = config

    async def build_vdi(self, profile: str = "release") -> Path:
        """
        Orquestra a criação de uma imagem VDI.
        
        1. Cria imagem RAW (FAT32) via WSL
        2. Converte para VDI via qemu-img
        """
        log.header("Criando Imagem VDI")
        
        # Garantir diretórios
        self.paths.ensure_dirs()
        
        raw_path = self.paths.dist_img / "redstone.raw"
        vdi_path = self.paths.dist_img / "redstone.vdi"
        
        # 1. Gerar RAW
        success = await self._create_raw_image(raw_path, profile)
        if not success:
            raise BuildError("Falha ao criar imagem RAW", "image")
            
        # 2. Converter para VDI
        success = await self._convert_to_vdi(raw_path, vdi_path)
        if not success:
            # Tentar limpar o raw mesmo em falha
            if raw_path.exists():
                raw_path.unlink()
            raise BuildError("Falha ao converter para VDI", "image")
            
        # Limpar RAW
        if raw_path.exists():
            raw_path.unlink()
            
        log.success(f"VDI criada com sucesso: {self.paths.relative(vdi_path)}")
        return vdi_path

    async def _create_raw_image(self, output: Path, profile: str) -> bool:
        """Cria imagem RAW formatada em FAT32 e copia o conteúdo do dist/qemu."""
        log.info(f"📂 Gerando imagem RAW ({output.name})...")
        
        # 1. Definir tamanho da imagem (provisório: 64MB)
        # TODO: Calcular dinamicamente com base no conteúdo
        img_size_mb = 64
        
        wsl_output = PathResolver.windows_to_wsl(output)
        wsl_dist = PathResolver.windows_to_wsl(self.paths.dist_qemu)
        
        # Comandos para rodar no WSL:
        # - Criar arquivo vazio de 64MB
        # - Formatar como FAT32
        # - Usar mcopy para copiar recursivamente o conteúdo (preserva estrutura)
        
        commands = [
            f"dd if=/dev/zero of='{wsl_output}' bs=1M count={img_size_mb}",
            f"mkfs.vfat -F 32 '{wsl_output}'",
            f"mcopy -i '{wsl_output}' -s '{wsl_dist}'/* ::/"
        ]
        
        full_cmd = " && ".join(commands)
        
        try:
            process = await asyncio.create_subprocess_exec(
                "wsl", "bash", "-c", full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                log.error(f"Erro no WSL ao criar RAW: {stderr.decode()}")
                return False
                
            log.step(f"RAW de {img_size_mb}MB formatado e populado")
            return True
            
        except Exception as e:
            log.error(f"Exceção ao criar RAW: {e}")
            return False

    async def _convert_to_vdi(self, source: Path, dest: Path) -> bool:
        """Converte imagem RAW para VDI usando qemu-img."""
        log.info(f"💾 Convertendo RAW para VDI ({dest.name})...")
        
        # Preferimos usar qemu-img do Windows se disponível, senão via WSL
        # No Windows geralmente está no PATH se o QEMU estiver instalado
        
        # Vamos tentar via WSL primeiro para manter consistência com o resto do build
        wsl_src = PathResolver.windows_to_wsl(source)
        wsl_dst = PathResolver.windows_to_wsl(dest)
        
        cmd = f"qemu-img convert -f raw -O vdi '{wsl_src}' '{wsl_dst}'"
        
        try:
            process = await asyncio.create_subprocess_exec(
                "wsl", "bash", "-c", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                # Se falhar no WSL, talvez o qemu-utils não esteja instalado lá
                log.warning("Falha ao converter via WSL, tentando host...")
                
                # Tentar comando direto no Windows
                process_win = await asyncio.create_subprocess_exec(
                    "qemu-img", "convert", "-f", "raw", "-O", "vdi", str(source), str(dest),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr_win = await process_win.communicate()
                
                if process_win.returncode != 0:
                    log.error(f"Falha ao converter via host também: {stderr_win.decode()}")
                    return False
            
            log.step(f"Conversão concluída: {dest.stat().st_size:,} bytes")
            return True
            
        except Exception as e:
            log.error(f"Exceção na conversão: {e}")
            return False
