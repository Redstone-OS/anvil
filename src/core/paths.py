"""
Anvil Core - Resolução de caminhos Windows/WSL
"""

from pathlib import Path, PurePosixPath
import os


class PathResolver:
    """Resolvedor de caminhos com conversão Windows ↔ WSL."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.anvil_root = self.project_root / "anvil"
    
    @classmethod
    def from_anvil_dir(cls) -> "PathResolver":
        """Cria resolver a partir do diretório do Anvil."""
        anvil_dir = Path(__file__).parent.parent.parent
        project_root = anvil_dir.parent
        return cls(project_root)
    
    # ========================================================================
    # Caminhos do Projeto
    # ========================================================================
    
    @property
    def forge(self) -> Path:
        """Caminho do kernel (forge)."""
        return self.project_root / "forge"
    
    @property
    def ignite(self) -> Path:
        """Caminho do bootloader (ignite)."""
        return self.project_root / "ignite"
    
    @property
    def services(self) -> Path:
        """Caminho dos serviços."""
        return self.project_root / "services"
    
    @property
    def dist(self) -> Path:
        """Caminho de distribuição."""
        return self.project_root / "dist"
    
    @property
    def dist_qemu(self) -> Path:
        """Caminho de distribuição para QEMU."""
        return self.dist / "qemu"
    
    @property
    def assets(self) -> Path:
        """Caminho de assets do Anvil."""
        return self.anvil_root / "assets"
    
    @property
    def ovmf(self) -> Path:
        """Caminho do OVMF.fd."""
        return self.assets / "OVMF.fd"
    
    @property
    def initramfs(self) -> Path:
        """Caminho do initramfs temporário."""
        return self.assets / "initramfs"
    
    # ========================================================================
    # Conversão Windows ↔ WSL
    # ========================================================================
    
    @staticmethod
    def windows_to_wsl(path: Path | str) -> str:
        """
        Converte caminho Windows para WSL.
        
        Exemplo: D:\\Github\\RedstoneOS → /mnt/d/Github/RedstoneOS
        """
        path = Path(path).resolve()
        path_str = str(path)
        
        # Extrair letra do drive e converter
        if len(path_str) >= 2 and path_str[1] == ":":
            drive_letter = path_str[0].lower()
            rest = path_str[2:].replace("\\", "/")
            return f"/mnt/{drive_letter}{rest}"
        
        # Fallback: apenas trocar barras
        return path_str.replace("\\", "/")
    
    @staticmethod
    def wsl_to_windows(path: str) -> Path:
        """
        Converte caminho WSL para Windows.
        
        Exemplo: /mnt/d/Github/RedstoneOS → D:\\Github\\RedstoneOS
        """
        if path.startswith("/mnt/") and len(path) >= 6:
            drive_letter = path[5].upper()
            rest = path[6:].replace("/", "\\")
            return Path(f"{drive_letter}:{rest}")
        
        # Fallback
        return Path(path.replace("/", "\\"))
    
    # ========================================================================
    # Artefatos de Build
    # ========================================================================
    
    def kernel_binary(self, profile: str = "release") -> Path:
        """Caminho do binário do kernel."""
        return self.forge / "target" / "x86_64-redstone" / profile / "forge"
    
    def bootloader_binary(self, profile: str = "release") -> Path:
        """Caminho do binário do bootloader."""
        return self.ignite / "target" / "x86_64-unknown-uefi" / profile / "ignite.efi"
    
    def service_binary(self, name: str, profile: str = "release") -> Path:
        """Caminho do binário de um serviço."""
        return self.services / name / "target" / "x86_64-unknown-none" / profile / name
    
    # ========================================================================
    # Logs
    # ========================================================================
    
    @property
    def serial_log(self) -> Path:
        """Caminho do log serial do QEMU."""
        return self.dist / "qemu-serial.log"
    
    @property
    def internal_log(self) -> Path:
        """Caminho do log interno do QEMU."""
        return self.dist / "qemu-internal.log"
    
    # ========================================================================
    # Utilitários
    # ========================================================================
    
    def ensure_dirs(self) -> None:
        """Garante que diretórios necessários existam."""
        dirs = [
            self.dist,
            self.dist_qemu,
            self.dist_qemu / "EFI" / "BOOT",
            self.dist_qemu / "boot",
            self.initramfs,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    def relative(self, path: Path) -> Path:
        """Retorna caminho relativo ao projeto."""
        try:
            return path.relative_to(self.project_root)
        except ValueError:
            return path
