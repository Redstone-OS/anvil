"""
Anvil Build - Criação do InitRAMFS
"""

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config import AnvilConfig
from core.logger import log
from core.paths import PathResolver
from core.exceptions import BuildError


@dataclass
class InitramfsEntry:
    """Entrada no InitRAMFS."""
    source: Path
    dest: str  # Caminho dentro do initramfs
    size: int = 0


class InitramfsBuilder:
    """Builder do InitRAMFS para o kernel."""
    
    # Estrutura padrão do RedstoneOS
    DIRECTORY_STRUCTURE = [
        "system/core",
        "system/services",
        "system/drivers",
        "system/manifests",
        "runtime/ipc",
        "runtime/logs",
        "state/system",
        "state/services",
    ]
    
    def __init__(self, paths: PathResolver, config: AnvilConfig):
        self.paths = paths
        self.config = config
        self.entries: list[InitramfsEntry] = []
    
    def prepare_structure(self) -> None:
        """Cria estrutura de diretórios do initramfs."""
        log.info("📂 Preparando estrutura InitRAMFS...")
        
        # Limpar se existir (User pediu para não apagar)
        # if self.paths.initramfs.exists():
        #     shutil.rmtree(self.paths.initramfs)
        
        # Criar estrutura
        for dir_path in self.DIRECTORY_STRUCTURE:
            full_path = self.paths.initramfs / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
        
        log.step("Estrutura: /system, /runtime, /state criada")
    
    def add_service(self, name: str, source: Path, is_core: bool = False) -> bool:
        """
        Adiciona serviço ao initramfs.
        
        Args:
            name: Nome do serviço
            source: Caminho do binário compilado
            is_core: Se True, vai para /system/core, senão /system/services
        """
        if not source.exists():
            log.warning(f"Serviço {name} não encontrado: {source}")
            return False
        
        dest_dir = "system/core" if is_core else "system/services"
        dest = f"{dest_dir}/{name}"
        
        # Copiar binário
        dest_path = self.paths.initramfs / dest
        shutil.copy2(source, dest_path)
        
        self.entries.append(InitramfsEntry(
            source=source,
            dest=dest,
            size=source.stat().st_size,
        ))
        
        log.step(f"/{dest} ({source.stat().st_size:,} bytes)")
        return True
    
    def create_services_manifest(self) -> None:
        """Cria manifesto de serviços."""
        manifest_path = self.paths.initramfs / "system/manifests/services.toml"
        
        content = """# Manifesto de Serviços - Redstone OS
# /system/manifests/services.toml

[init]
path = "/system/core/init"
restart = "never"
depends = []

# [console]
# path = "/system/services/console"
# restart = "always"
# depends = []
"""
        
        manifest_path.write_text(content, encoding="utf-8")
        log.step("/system/manifests/services.toml criado")
    
    async def create_tar(self, output_path: Path) -> Optional[int]:
        """
        Cria arquivo TAR do initramfs via WSL.
        
        Returns:
            Tamanho do arquivo em bytes, ou None se falhou
        """
        log.info("📦 Criando initfs (tar via WSL)...")
        
        wsl_initramfs = PathResolver.windows_to_wsl(self.paths.initramfs)
        wsl_output = PathResolver.windows_to_wsl(output_path)
        
        cmd = f"tar -cf '{wsl_output}' -C '{wsl_initramfs}' ."
        
        try:
            process = await asyncio.create_subprocess_exec(
                "wsl", "bash", "-c", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                log.error(f"Falha ao criar TAR: {stderr.decode()}")
                return None
            
            size = output_path.stat().st_size
            log.success(f"initfs criado ({size / 1024:.2f} KB)")
            return size
            
        except FileNotFoundError:
            log.error("WSL não disponível")
            return None
    
    async def build(self, profile: str = "release") -> bool:
        """
        Processo completo de build do initramfs.
        """
        log.header("Criando InitRAMFS")
        
        # Preparar estrutura
        self.prepare_structure()
        
        # Adicionar supervisor (PID 1)
        supervisor_path = self.paths.service_binary("supervisor", profile)
        # is_core=False -> /system/services/supervisor (conforme user request)
        if not self.add_service("supervisor", supervisor_path, is_core=False):
            raise BuildError("Serviço supervisor é obrigatório", "initramfs")
        
        # Adicionar outros serviços
        for svc in self.config.components.services:
            if svc.name == "supervisor":
                continue
            # Usar path do config (suporta paths customizados como firefly/compositor)
            svc_path = self.paths.service_binary_from_config(svc.path, svc.name, profile)
            self.add_service(svc.name, svc_path)
        
        # Criar manifesto
        self.create_services_manifest()
        
        # Criar TAR
        output = self.paths.dist_qemu / "boot" / "initfs"
        output.parent.mkdir(parents=True, exist_ok=True)
        
        tar_size = await self.create_tar(output)
        
        return tar_size is not None
