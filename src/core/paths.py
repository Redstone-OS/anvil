"""Anvil Core - Gerenciamento de caminhos e utilitários de sistema de arquivos."""

from __future__ import annotations
from pathlib import Path
from typing import Optional

class Paths:
    """
    Gerenciador centralizado de caminhos do projeto.
    
    Responsabilidades:
    - Definir a estrutura de diretórios do RedstoneOS.
    - Converter caminhos entre Windows e WSL (necessário pois QEMU/GCC rodam via WSL).
    - Localizar artefatos de build.
    """
    
    def __init__(self, project_root: Path):
        self._root = project_root.resolve()
        
    @classmethod
    def from_anvil_dir(cls) -> Paths:
        """Cria instância baseado na localização deste arquivo."""
        anvil_dir = Path(__file__).parent.parent.parent.parent
        project_root = anvil_dir.parent
        return cls(project_root)
        
    # Pastas Principais
    @property
    def root(self) -> Path: return self._root
    
    @property
    def anvil(self) -> Path: return self._root / "anvil"
    
    @property
    def forge(self) -> Path: return self._root / "forge"  # Kernel
    
    @property
    def ignite(self) -> Path: return self._root / "ignite"  # Bootloader
    
    @property
    def services(self) -> Path: return self._root / "services"
    
    @property
    def firefly(self) -> Path: return self._root / "firefly"  # GUI
    
    @property
    def lib(self) -> Path: return self._root / "lib"
    
    @property
    def sdk(self) -> Path: return self._root / "sdk"
    
    @property
    def dist(self) -> Path: return self._root / "dist"  # Saída build
    
    @property
    def dist_qemu(self) -> Path: return self.dist / "qemu"  # Raiz FS do QEMU
    
    @property
    def dist_img(self) -> Path: return self.dist / "img"  # Imagens VDI/Raw
    
    @property
    def assets(self) -> Path: return self.anvil / "src" / "assets"
    
    @property
    def initramfs(self) -> Path: return self.assets / "initramfs"
    
    # Artefatos compilados
    def kernel_binary(self, profile: str = "release") -> Path:
        return self.forge / "target" / "x86_64-redstone" / profile / "forge"
        
    def bootloader_binary(self, profile: str = "release") -> Path:
        return self.ignite / "target" / "x86_64-unknown-uefi" / profile / "ignite.efi"
        
    def service_binary(self, name: str, profile: str = "release", base_path: Optional[Path] = None) -> Path:
        base = base_path or (self.services / name)
        return base / "target" / "x86_64-unknown-none" / profile / name

    # UEFI / BIOS
    @property
    def ovmf(self) -> Path: return self.assets / "OVMF.fd"
    
    @property
    def ignite_cfg(self) -> Path: return self.assets / "ignite.cfg"

    # Conversão WSL (Windows Subsystem for Linux)
    @staticmethod
    def to_wsl(path: Path | str) -> str:
        """
        Converte caminho Windows (D:\...) para WSL (/mnt/d/...).
        Essencial para passar caminhos para ferramentas rodando no WSL (gcc, qemu).
        """
        path = Path(path).resolve()
        path_str = str(path)
        if len(path_str) >= 2 and path_str[1] == ":":
            drive = path_str[0].lower()
            rest = path_str[2:].replace("\\", "/")
            return f"/mnt/{drive}{rest}"
        return path_str.replace("\\", "/")

    @staticmethod
    def from_wsl(wsl_path: str) -> Path:
        """Converte caminho WSL de volta para Windows."""
        if wsl_path.startswith("/mnt/") and len(wsl_path) >= 6:
            drive = wsl_path[5].upper()
            rest = wsl_path[6:].replace("/", "\\")
            return Path(f"{drive}:{rest}")
        return Path(wsl_path.replace("/", "\\"))

    def ensure_dirs(self) -> None:
        """Garante que todas as pastas de saída existam."""
        dirs = [
            self.dist,
            self.dist_qemu,
            self.dist_img,
            self.dist_qemu / "EFI" / "BOOT",
            self.dist_qemu / "boot",
            self.dist_qemu / "system" / "services",
            self.dist_qemu / "apps" / "system",
            self.dist_qemu / "system" / "manifests" / "services",
            self.dist_qemu / "system" / "manifests" / "apps",
            self.initramfs,
            self.anvil_log_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
