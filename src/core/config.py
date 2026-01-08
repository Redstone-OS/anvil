"""Anvil Core - Carregamento de configurações."""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import toml

from core.errors import ConfigError

@dataclass
class ServiceConfig:
    """Configuração de um serviço."""
    name: str
    path: str
    target: str = "x86_64-unknown-none"
    core: bool = False

@dataclass
class KernelConfig:
    """Configuração do Kernel."""
    path: str = "forge"
    target: str = "x86_64-redstone"
    default_profile: str = "release"

@dataclass
class BootloaderConfig:
    """Configuração do Bootloader."""
    path: str = "ignite"
    target: str = "x86_64-unknown-uefi"
    default_profile: str = "release"

@dataclass
class QemuLogging:
    """Configuração de flags de log do QEMU (-d ...)."""
    flags: list[str] = field(default_factory=lambda: ["cpu_reset", "int", "mmu", "guest_errors", "unimp"])

@dataclass
class AnalysisPattern:
    """Padrão de erro para análise automática de logs."""
    name: str
    trigger: str
    diagnosis: str
    solution: str
    severity: str = "warning"

@dataclass
class AnalysisConfig:
    """Configuração do sistema de análise."""
    context_lines: int = 100
    auto_inspect_binary: bool = True
    stop_on_exception: bool = True
    patterns: list[AnalysisPattern] = field(default_factory=list)

@dataclass
class AppConfig:
    """Configuração de aplicativos."""
    name: str
    path: str
    target: str = "x86_64-unknown-none"

@dataclass
class ComponentsConfig:
    """Agrupamento de todos os componentes do sistema."""
    kernel: KernelConfig = field(default_factory=KernelConfig)
    bootloader: BootloaderConfig = field(default_factory=BootloaderConfig)
    services: list[ServiceConfig] = field(default_factory=list)
    apps: list[AppConfig] = field(default_factory=list)

@dataclass
class Config:
    """Classe principal de configuração (mapeada do anvil.toml)."""
    project_name: str = "RedstoneOS"
    project_root: Path = field(default_factory=Path)
    components: ComponentsConfig = field(default_factory=ComponentsConfig)
    qemu: QemuConfig = field(default_factory=QemuConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any], config_path: Path) -> Config:
        """Cria objeto Config a partir de dicionário (toml)."""
        project_data = data.get("project", {})
        root_str = project_data.get("root", "..")
        project_root = (config_path.parent / root_str).resolve()
        
        comp_data = data.get("components", {})
        kernel = KernelConfig(**comp_data.get("kernel", {}))
        bootloader = BootloaderConfig(**comp_data.get("bootloader", {}))
        
        services = [ServiceConfig(**s) for s in comp_data.get("services", [])]
        apps = [AppConfig(**a) for a in comp_data.get("apps", [])]
        
        components = ComponentsConfig(kernel=kernel, bootloader=bootloader, services=services, apps=apps)
        
        qemu_data = data.get("qemu", {}).copy()
        logging_data = qemu_data.pop("logging", {})
        qemu_logging = QemuLogging(**logging_data)
        qemu = QemuConfig(**qemu_data, logging=qemu_logging)
        
        analysis_data = data.get("analysis", {}).copy()
        patterns = [AnalysisPattern(**p) for p in analysis_data.pop("patterns", [])]
        analysis = AnalysisConfig(**analysis_data, patterns=patterns)
        
        return cls(
            project_name=project_data.get("name", "RedstoneOS"),
            project_root=project_root,
            components=components,
            qemu=qemu,
            analysis=analysis,
        )

def find_config_file() -> Path:
    """Procura pelo arquivo anvil.toml em locais padrão."""
    search_paths = [
        Path.cwd() / "anvil.toml",
        Path.cwd().parent / "anvil" / "anvil.toml",
        Path(__file__).parent.parent.parent.parent / "anvil.toml",
    ]
    for path in search_paths:
        if path.exists(): return path
    raise ConfigError("anvil.toml não encontrado", f"Procurado em: {[str(p) for p in search_paths]}")

def load_config(config_path: Optional[Path] = None) -> Config:
    """Carrega e analisa o arquivo de configuração."""
    from core.logger import get_logger
    logger = get_logger()
    
    if config_path is None:
        config_path = find_config_file()
    
    logger.info(f"Carregando config de: {config_path.absolute()}")
    
    if not config_path.exists():
        logger.error(f"Arquivo não encontrado: {config_path}")
        raise ConfigError(f"Arquivo de config não achado: {config_path}")
    
    try:
        data = toml.load(config_path)
        return Config.from_dict(data, config_path)
    except Exception as e:
        logger.error(f"Erro ao carregar config: {e}")
        raise ConfigError(f"Falha ao carregar config: {config_path}", str(e))
