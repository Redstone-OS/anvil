"""Anvil Build - Preparador de Distribuição.

Este módulo organiza o diretório 'dist/qemu' que simula o disco rígido do QEMU.
Copia Kernel, Bootloader e cria arquivos de configuração UEFI.
"""

import shutil
from pathlib import Path
from typing import Optional

from core.config import Config
from core.paths import Paths
from core.errors import BuildError
from core.logger import Logger, get_logger

class DistBuilder:
    def __init__(self, paths: Paths, config: Config, log: Optional[Logger] = None):
        self.paths = paths
        self.config = config
        self.log = log or get_logger()
        
    def prepare(self, profile: str = "release") -> bool:
        """
        Executa a preparação completa da pasta de distribuição.
        Copia binários e configura o bootloader.
        """
        self.log.header("Preparando Distribuição")
        self._create_structure()
        
        if not self._copy_bootloader(profile):
            raise BuildError("Bootloader é necessário", "dist")
            
        if not self._copy_kernel(profile):
            raise BuildError("Kernel é necessário", "dist")
            
        self._create_ignite_cfg()
        self.log.success(f"dist/qemu pronto: {self.paths.dist_qemu}")
        return True
        
    def _create_structure(self) -> None:
        """Cria a árvore de diretórios necessária (EFI, boot, system...)."""
        self.log.info("Criando estrutura de diretórios...")
        (self.paths.dist_qemu / "EFI" / "BOOT").mkdir(parents=True, exist_ok=True)
        (self.paths.dist_qemu / "boot").mkdir(parents=True, exist_ok=True)
        (self.paths.dist_qemu / "system" / "services").mkdir(parents=True, exist_ok=True)
        self.log.step("Estrutura criada: EFI/BOOT, boot, system/services")
        
    def _copy_bootloader(self, profile: str) -> bool:
        """Copia ignite.efi para EFI/BOOT/BOOTX64.EFI."""
        source = self.paths.bootloader_binary(profile)
        dest = self.paths.dist_qemu / "EFI" / "BOOT" / "BOOTX64.EFI"
        if not source.exists():
            self.log.error(f"Bootloader não encontrado: {source}")
            return False
        shutil.copy2(source, dest)
        self.log.step(f"Bootloader copiado para EFI/BOOT/BOOTX64.EFI")
        return True
        
    def _copy_kernel(self, profile: str) -> bool:
        """Copia forge (kernel) para boot/kernel."""
        source = self.paths.kernel_binary(profile)
        dest = self.paths.dist_qemu / "boot" / "kernel"
        if not source.exists():
            self.log.error(f"Kernel não encontrado: {source}")
            return False
        shutil.copy2(source, dest)
        self.log.step(f"Kernel copiado para boot/kernel")
        return True
        
    def _create_ignite_cfg(self) -> None:
        """Gera o arquivo de configuração ignite.cfg para o bootloader."""
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
        self.log.step("ignite.cfg criado")
