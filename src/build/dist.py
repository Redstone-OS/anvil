"""
Anvil Build - Preparação do diretório de distribuição
"""

import shutil
from pathlib import Path

from core.config import AnvilConfig
from core.logger import log
from core.paths import PathResolver
from core.exceptions import BuildError


class DistBuilder:
    """Prepara o diretório dist/qemu para execução."""
    
    def __init__(self, paths: PathResolver, config: AnvilConfig):
        self.paths = paths
        self.config = config
    
    def clean(self) -> None:
        """Limpa diretório de distribuição."""
        # Se habilitado, pode apagar tudo. Mas por padrão agora apenas garante a existência.
        # if self.paths.dist_qemu.exists():
        #     shutil.rmtree(self.paths.dist_qemu)
        self.paths.dist_qemu.mkdir(parents=True, exist_ok=True)
        log.step("dist/qemu preservado (clean desativado)")
    
    def prepare_structure(self) -> None:
        """Cria estrutura UEFI."""
        log.info("📦 Preparando dist/qemu...")
        
        # Estrutura UEFI
        efi_boot = self.paths.dist_qemu / "EFI" / "BOOT"
        boot = self.paths.dist_qemu / "boot"
        
        efi_boot.mkdir(parents=True, exist_ok=True)
        boot.mkdir(parents=True, exist_ok=True)
        
        log.step("Estrutura EFI/BOOT e boot criada")
    
    def copy_bootloader(self, profile: str = "release") -> bool:
        """Copia bootloader para dist."""
        source = self.paths.bootloader_binary(profile)
        dest = self.paths.dist_qemu / "EFI" / "BOOT" / "BOOTX64.EFI"
        
        if not source.exists():
            log.error(f"Bootloader não encontrado: {source}")
            return False
        
        shutil.copy2(source, dest)
        log.step(f"Bootloader → EFI/BOOT/BOOTX64.EFI ({source.stat().st_size:,} bytes)")
        return True
    
    def copy_kernel(self, profile: str = "release") -> bool:
        """Copia kernel para dist."""
        source = self.paths.kernel_binary(profile)
        dest = self.paths.dist_qemu / "boot" / "kernel"
        
        if not source.exists():
            log.error(f"Kernel não encontrado: {source}")
            return False
        
        shutil.copy2(source, dest)
        log.step(f"Kernel → boot/kernel ({source.stat().st_size:,} bytes)")
        return True
    
    def copy_assets(self) -> None:
        """Copia assets necessários."""
        # UEFI Shell (opcional)
        shell_source = self.paths.assets / "shellx64.efi"
        if shell_source.exists():
            shell_dest = self.paths.dist_qemu / "EFI" / "BOOT" / "shellx64.efi"
            shutil.copy2(shell_source, shell_dest)
            log.step("UEFI Shell copiado")
        
        # Config do bootloader
        config_source = self.paths.assets / "ignite.cfg"
        if config_source.exists():
            config_dest = self.paths.dist_qemu / "ignite.cfg"
            shutil.copy2(config_source, config_dest)
            log.step("ignite.cfg copiado")
    
    def prepare(self, profile: str = "release") -> bool:
        """
        Processo completo de preparação do dist.
        
        Returns:
            True se sucesso, False se algum artefato obrigatório falhou
        """
        log.header("Preparando Distribuição")
        
        # Limpar e criar estrutura
        self.clean()
        self.prepare_structure()
        
        # Copiar bootloader (obrigatório)
        if not self.copy_bootloader(profile):
            raise BuildError("Bootloader é obrigatório", "dist")
        
        # Copiar kernel (obrigatório)
        if not self.copy_kernel(profile):
            raise BuildError("Kernel é obrigatório", "dist")
        
        # Assets
        self.copy_assets()
        
        log.success(f"dist/qemu pronto: {self.paths.dist_qemu}")
        return True
