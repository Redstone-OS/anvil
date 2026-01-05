"""Anvil Core - Configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import toml

from core.errors import ConfigError


@dataclass
class ServiceConfig:
    """Service component configuration."""
    name: str
    path: str
    target: str = "x86_64-unknown-none"
    core: bool = False  # Is it a core service (/system/core vs /system/services)


@dataclass
class KernelConfig:
    """Kernel configuration."""
    path: str = "forge"
    target: str = "x86_64-redstone"
    default_profile: str = "release"


@dataclass
class BootloaderConfig:
    """Bootloader configuration."""
    path: str = "ignite"
    target: str = "x86_64-unknown-uefi"
    default_profile: str = "release"


@dataclass
class QemuLogging:
    """QEMU debug logging configuration."""
    flags: list[str] = field(default_factory=lambda: [
        "cpu_reset", "int", "mmu", "guest_errors", "unimp"
    ])
    serial_file: str = "../dist/qemu-serial.log"
    internal_file: str = "../dist/qemu-internal.log"


@dataclass
class QemuConfig:
    """QEMU execution configuration."""
    memory: str = "512M"
    vga_memory: int = 256
    ovmf: str = "/usr/share/qemu/OVMF.fd"
    serial: str = "stdio"
    monitor: str = "none"
    drive_interface: str = "ide"
    enable_gdb: bool = False
    gdb_port: int = 1234
    extra_args: list[str] = field(default_factory=lambda: ["-no-reboot", "-no-shutdown"])
    logging: QemuLogging = field(default_factory=QemuLogging)
    debug_flags: Optional[list[str]] = None


@dataclass
class AnalysisPattern:
    """Error pattern for automatic diagnosis."""
    name: str
    trigger: str  # Regex pattern
    diagnosis: str
    solution: str
    severity: str = "warning"


@dataclass
class AnalysisConfig:
    """Analysis and diagnostics configuration."""
    context_lines: int = 100
    auto_inspect_binary: bool = True
    stop_on_exception: bool = True
    patterns: list[AnalysisPattern] = field(default_factory=list)


@dataclass
class AppConfig:
    """User-space application configuration."""
    name: str
    path: str
    target: str = "x86_64-unknown-none"

@dataclass
class ComponentsConfig:
    """All project components."""
    kernel: KernelConfig = field(default_factory=KernelConfig)
    bootloader: BootloaderConfig = field(default_factory=BootloaderConfig)
    services: list[ServiceConfig] = field(default_factory=list)
    apps: list[AppConfig] = field(default_factory=list)


@dataclass
class Config:
    """
    Main Anvil configuration.
    
    Loaded from toml in the anvil/ directory.
    """
    project_name: str = "RedstoneOS"
    project_root: Path = field(default_factory=Path)
    components: ComponentsConfig = field(default_factory=ComponentsConfig)
    qemu: QemuConfig = field(default_factory=QemuConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any], config_path: Path) -> Config:
        """Parse configuration from TOML dictionary."""
        # Resolve project root relative to config file
        project_data = data.get("project", {})
        root_str = project_data.get("root", "..")
        project_root = (config_path.parent / root_str).resolve()
        
        # Parse components
        comp_data = data.get("components", {})
        
        kernel = KernelConfig(**comp_data.get("kernel", {}))
        bootloader = BootloaderConfig(**comp_data.get("bootloader", {}))
        
        services = []
        for svc in comp_data.get("services", []):
            services.append(ServiceConfig(**svc))

        apps = []
        for app in comp_data.get("apps", []):
            apps.append(AppConfig(**app))
        
        components = ComponentsConfig(
            kernel=kernel,
            bootloader=bootloader,
            services=services,
            apps=apps,
        )
        
        # Parse QEMU config
        qemu_data = data.get("qemu", {}).copy()
        logging_data = qemu_data.pop("logging", {})
        qemu_logging = QemuLogging(**logging_data)
        
        qemu = QemuConfig(**qemu_data, logging=qemu_logging)
        from core.logger import get_logger
        get_logger().info(f"DEBUG: drive_interface carregado: {qemu.drive_interface}")
        
        # Parse analysis config
        analysis_data = data.get("analysis", {}).copy()
        patterns_data = analysis_data.pop("patterns", [])
        patterns = [AnalysisPattern(**p) for p in patterns_data]
        analysis = AnalysisConfig(**analysis_data, patterns=patterns)
        
        return cls(
            project_name=project_data.get("name", "RedstoneOS"),
            project_root=project_root,
            components=components,
            qemu=qemu,
            analysis=analysis,
        )


def find_config_file() -> Path:
    """
    Find anvil.toml configuration file.
    
    Search order:
    1. Current directory
    2. Parent/anvil/ (if CWD is project root)
    3. Script package location
    """
    search_paths = [
        Path.cwd() / "anvil.toml",
        Path.cwd().parent / "anvil" / "anvil.toml",
        Path(__file__).parent.parent.parent.parent / "anvil.toml",
    ]
    
    for path in search_paths:
        if path.exists():
            return path
    
    raise ConfigError(
        "anvil.toml not found",
        f"Searched in: {[str(p) for p in search_paths]}",
    )


def load_config(config_path: Optional[Path] = None) -> Config:
    """
    Load configuration from TOML file.
    """
    from core.logger import get_logger
    logger = get_logger()
    
    if config_path is None:
        config_path = find_config_file()
    
    logger.info(f"📂 Carregando config de: {config_path.absolute()}")
    
    if not config_path.exists():
        logger.error(f"❌ Arquivo não encontrado: {config_path}")
        raise ConfigError(f"Config file not found: {config_path}")
    
    try:
        data = toml.load(config_path)
        return Config.from_dict(data, config_path)
    except Exception as e:
        logger.error(f"❌ Erro ao carregar config: {e}")
        raise ConfigError(f"Failed to load config: {config_path}", str(e))

