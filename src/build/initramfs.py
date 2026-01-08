"""Anvil Build - Gerador de InitRAMFS.

Responsável por:
1. Criar o arquivo initfs (TAR) contendo o Supervisor.
2. Copiar serviços e apps para as pastas apropriadas no 'disco' (dist/qemu).
3. Gerar manifestos de serviços.
"""

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
    source: Path
    dest: str
    size: int = 0

class InitramfsBuilder:
    INITFS_DIRECTORIES = ["system/core"]
    
    def __init__(self, paths: Paths, config: Config, log: Optional[Logger] = None):
        self.paths = paths
        self.config = config
        self.log = log or get_logger()
        self.entries = []
        
    async def build(self, profile: str = "release") -> bool:
        """Executa processo de build do initramfs e deploy de componentes."""
        self.log.header("Construindo InitRAMFS e Serviços")
        
        self._clean_staging()
        self._create_initfs_structure()
        
        # O Supervisor é o único binário que VAI DENTRO do initfs (boot)
        supervisor_path = self.paths.service_binary("supervisor", profile)
        if not self._add_to_initfs("supervisor", supervisor_path):
            raise BuildError("Supervisor é necessário", "initramfs")
            
        # Cria o pacote TAR do initfs
        output = self.paths.dist_qemu / "boot" / "initfs"
        output.parent.mkdir(parents=True, exist_ok=True)
        if await self._create_tar(output) is None: return False
        
        # Outros serviços e apps vão para o sistema de arquivos normal (/system/services)
        await self._deploy_services(profile)
        await self._deploy_apps(profile)
        self._create_manifest()
        
        return True
        
    def _clean_staging(self):
        """Limpa diretório temporário do initramfs."""
        if self.paths.initramfs.exists(): shutil.rmtree(self.paths.initramfs)
        self.paths.initramfs.mkdir(parents=True, exist_ok=True)
        
    def _create_initfs_structure(self):
        """Cria pastas básicas."""
        self.log.info("Criando estrutura mínima do initfs...")
        for dir_path in self.INITFS_DIRECTORIES:
            (self.paths.initramfs / dir_path).mkdir(parents=True, exist_ok=True)
            
    def _add_to_initfs(self, name: str, source: Path) -> bool:
        """Adiciona arquivo ao staging do initramfs."""
        if not source.exists():
            self.log.error(f"Serviço '{name}' não encontrado: {source}")
            return False
        dest = f"system/core/{name}"
        dest_path = self.paths.initramfs / dest
        shutil.copy2(source, dest_path)
        self.log.step(f"initfs: /{dest}")
        return True
        
    async def _deploy_services(self, profile: str):
        """Copia serviços para dist/qemu/system/services."""
        self.log.info("Implantando serviços...")
        services_dir = self.paths.dist_qemu / "system" / "services"
        services_dir.mkdir(parents=True, exist_ok=True)
        
        for svc in self.config.components.services:
            if svc.name == "supervisor": continue # Já foi pro initfs
            
            svc_path = self.paths.service_binary(svc.name, profile, base_path=self.paths.root / svc.path)
            
            if not svc_path.exists():
                self.log.warning(f"Serviço '{svc.name}' não achado")
                continue
                
            # Estrutura: nome_servico/nome_servico.app
            dest_dir = services_dir / svc.name
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(svc_path, dest_dir / f"{svc.name}.app")
            self.log.step(f"Deploy: {svc.name}")
            
    async def _deploy_apps(self, profile: str):
        """Copia apps para dist/qemu/apps/system."""
        self.log.info("Implantando apps...")
        apps_dir = self.paths.dist_qemu / "apps" / "system"
        apps_dir.mkdir(parents=True, exist_ok=True)
        
        for app in self.config.components.apps:
            app_path = self.paths.service_binary(app.name, profile, base_path=self.paths.root / app.path)
            
            if not app_path.exists():
                self.log.warning(f"App '{app.name}' não achado")
                continue
                
            dest_dir = apps_dir / app.name
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(app_path, dest_dir / f"{app.name}.app")
            self.log.step(f"Deploy: {app.name}")
            
    def _create_manifest(self):
        """Gera arquivo services.toml listando serviços para o Supervisor."""
        manifests_dir = self.paths.dist_qemu / "system" / "manifests" / "services"
        manifests_dir.mkdir(parents=True, exist_ok=True)
        
        lines = ["# RedstoneOS Services Manifest", ""]
        for svc in self.config.components.services:
            if svc.name == "supervisor": continue
            
            lines.extend([
                "[[service]]",
                f'name = "{svc.name}"',
                f'path = "/system/services/{svc.name}/{svc.name}.app"',
                'restart = "always"',
                ""
            ])
            
        (manifests_dir / "services.toml").write_text("\n".join(lines), encoding="utf-8")
        self.log.step("Manifesto de serviços criado")

    async def _create_tar(self, output: Path) -> Optional[int]:
        """Usa 'tar' via WSL para criar o arquivo initfs com permissões corretas."""
        self.log.info("Criando arquivo TAR initfs...")
        
        wsl_init = Paths.to_wsl(self.paths.initramfs)
        wsl_out = Paths.to_wsl(output)
        
        # -C muda o diretório antes de compactar, '.' pega tudo
        cmd = f"tar -cf '{wsl_out}' -C '{wsl_init}' ."
        
        try:
            p = await asyncio.create_subprocess_exec(
                "wsl", "bash", "-c", cmd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            _, err = await p.communicate()
            
            if p.returncode != 0:
                self.log.error(f"Erro no TAR: {err.decode()}")
                return None
                
            return output.stat().st_size
        except Exception as e:
            self.log.error(f"Erro ao chamar WSL: {e}")
            return None
