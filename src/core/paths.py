"""Anvil Core - Path resolution with Windows/WSL conversion."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Optional


class Paths:
    """
    Centralized path management for the RedstoneOS project.
    
    Handles:
    - Project directory structure
    - Windows ↔ WSL path conversion
    - Build artifact locations
    """
    
    def __init__(self, project_root: Path):
        self._root = project_root.resolve()
    
    @classmethod
    def from_anvil_dir(cls) -> Paths:
        """Create Paths from the anvil package location."""
        # anvil/src/anvil/core/paths.py -> anvil/
        anvil_dir = Path(__file__).parent.parent.parent.parent
        project_root = anvil_dir.parent
        return cls(project_root)
    
    @classmethod
    def auto_detect(cls) -> Paths:
        """
        Auto-detect project root by searching for anvil.toml.
        
        Searches:
        1. Current working directory
        2. Parent of CWD (if in anvil/)
        3. Parent of script location
        """
        search_paths = [
            Path.cwd() / "anvil.toml",
            Path.cwd().parent / "anvil" / "anvil.toml",
            Path(__file__).parent.parent.parent.parent / "anvil.toml",
        ]
        
        for path in search_paths:
            if path.exists():
                return cls(path.parent.parent)
        
        # Fallback to CWD parent
        return cls(Path.cwd().parent)
    
    # =========================================================================
    # Root Directories
    # =========================================================================
    
    @property
    def root(self) -> Path:
        """Project root directory."""
        return self._root
    
    @property
    def anvil(self) -> Path:
        """Anvil tool directory."""
        return self._root / "anvil"
    
    @property
    def forge(self) -> Path:
        """Kernel (forge) directory."""
        return self._root / "forge"
    
    @property
    def ignite(self) -> Path:
        """Bootloader (ignite) directory."""
        return self._root / "ignite"
    
    @property
    def services(self) -> Path:
        """Services directory."""
        return self._root / "services"
    
    @property
    def firefly(self) -> Path:
        """Firefly GUI subsystem directory."""
        return self._root / "firefly"
    
    @property
    def dist(self) -> Path:
        """Distribution output directory."""
        return self._root / "dist"
    
    @property
    def dist_qemu(self) -> Path:
        """QEMU-ready distribution."""
        return self.dist / "qemu"
    
    @property
    def dist_img(self) -> Path:
        """Disk images output."""
        return self.dist / "img"
    
    @property
    def assets(self) -> Path:
        """Anvil assets directory."""
        return self.anvil / "src" / "assets"
    
    @property
    def initramfs(self) -> Path:
        """InitRAMFS staging directory."""
        return self.assets / "initramfs"
    
    # =========================================================================
    # Build Artifacts
    # =========================================================================
    
    def kernel_binary(self, profile: str = "release") -> Path:
        """Path to compiled kernel binary."""
        return self.forge / "target" / "x86_64-redstone" / profile / "forge"
    
    def bootloader_binary(self, profile: str = "release") -> Path:
        """Path to compiled bootloader."""
        return self.ignite / "target" / "x86_64-unknown-uefi" / profile / "ignite.efi"
    
    def service_binary(
        self,
        name: str,
        profile: str = "release",
        base_path: Optional[Path] = None,
    ) -> Path:
        """Path to compiled service binary."""
        base = base_path or (self.services / name)
        return base / "target" / "x86_64-unknown-none" / profile / name
    
    # =========================================================================
    # Log Files
    # =========================================================================
    
    @property
    def serial_log(self) -> Path:
        """QEMU serial output log."""
        return self.dist / "qemu-serial.log"
    
    @property
    def cpu_log(self) -> Path:
        """QEMU internal CPU log (-D)."""
        return self.dist / "qemu-internal.log"
    
    @property
    def anvil_log_dir(self) -> Path:
        """Anvil's internal logs."""
        return self.anvil / "src" / "log"
    
    # =========================================================================
    # UEFI Assets
    # =========================================================================
    
    @property
    def ovmf(self) -> Path:
        """OVMF UEFI firmware."""
        return self.assets / "OVMF.fd"
    
    @property
    def ignite_cfg(self) -> Path:
        """Bootloader configuration."""
        return self.assets / "ignite.cfg"
    
    # =========================================================================
    # Path Conversion
    # =========================================================================
    
    @staticmethod
    def to_wsl(path: Path | str) -> str:
        """
        Convert Windows path to WSL path.
        
        Example: D:\\Github\\RedstoneOS -> /mnt/d/Github/RedstoneOS
        """
        path = Path(path).resolve()
        path_str = str(path)
        
        # Extract drive letter
        if len(path_str) >= 2 and path_str[1] == ":":
            drive = path_str[0].lower()
            rest = path_str[2:].replace("\\", "/")
            return f"/mnt/{drive}{rest}"
        
        return path_str.replace("\\", "/")
    
    @staticmethod
    def from_wsl(wsl_path: str) -> Path:
        """
        Convert WSL path to Windows path.
        
        Example: /mnt/d/Github/RedstoneOS -> D:\\Github\\RedstoneOS
        """
        if wsl_path.startswith("/mnt/") and len(wsl_path) >= 6:
            drive = wsl_path[5].upper()
            rest = wsl_path[6:].replace("/", "\\")
            return Path(f"{drive}:{rest}")
        
        return Path(wsl_path.replace("/", "\\"))
    
    # =========================================================================
    # Utilities
    # =========================================================================
    
    def ensure_dirs(self) -> None:
        """Create all required directories."""
        dirs = [
            self.dist,
            self.dist_qemu,
            self.dist_img,
            self.dist_qemu / "EFI" / "BOOT",
            self.dist_qemu / "boot",
            self.dist_qemu / "system" / "services",
            self.initramfs,
            self.anvil_log_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    def relative(self, path: Path) -> Path:
        """Get path relative to project root."""
        try:
            return path.relative_to(self._root)
        except ValueError:
            return path
    
    def resolve(self, relative_path: str | Path) -> Path:
        """Resolve a path relative to project root."""
        return (self._root / relative_path).resolve()
