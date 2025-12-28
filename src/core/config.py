"""
Anvil Core - Configuração centralizada
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import toml

from core.exceptions import ConfigError


@dataclass
class ServiceConfig:
    """Configuração de um serviço."""
    name: str
    path: str
    target: str = "x86_64-unknown-none"


@dataclass
class KernelConfig:
    """Configuração do kernel."""
    path: str = "forge"
    target: str = "x86_64-redstone"
    default_profile: str = "release"


@dataclass
class BootloaderConfig:
    """Configuração do bootloader."""
    path: str = "ignite"
    target: str = "x86_64-unknown-uefi"
    default_profile: str = "release"


@dataclass
class QemuLoggingConfig:
    """Configuração de logging do QEMU."""
    flags: list[str] = field(default_factory=lambda: [
        "cpu_reset", "int", "mmu", "guest_errors", "unimp"
    ])
    serial_file: str = "../dist/qemu-serial.log"
    internal_file: str = "../dist/qemu-internal.log"


@dataclass
class QemuConfig:
    """Configuração do QEMU."""
    memory: str = "512M"
    ovmf: str = "assets/OVMF.fd"
    extra_args: list[str] = field(default_factory=list)
    logging: QemuLoggingConfig = field(default_factory=QemuLoggingConfig)


@dataclass
class PatternConfig:
    """Configuração de um padrão de erro."""
    name: str
    trigger: str
    diagnosis: str
    solution: str
    severity: str = "warning"


@dataclass
class AnalysisConfig:
    """Configuração de análise."""
    context_lines: int = 100
    auto_inspect_binary: bool = True
    stop_on_exception: bool = True
    patterns: list[PatternConfig] = field(default_factory=list)


@dataclass
class ComponentsConfig:
    """Configuração de componentes."""
    kernel: KernelConfig = field(default_factory=KernelConfig)
    bootloader: BootloaderConfig = field(default_factory=BootloaderConfig)
    services: list[ServiceConfig] = field(default_factory=list)


@dataclass
class AnvilConfig:
    """Configuração principal do Anvil."""
    project_name: str = "RedstoneOS"
    project_root: Path = field(default_factory=Path)
    components: ComponentsConfig = field(default_factory=ComponentsConfig)
    qemu: QemuConfig = field(default_factory=QemuConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any], config_path: Path) -> "AnvilConfig":
        """Cria configuração a partir de dicionário."""
        # Resolver root relativo ao config
        project_data = data.get("project", {})
        root_str = project_data.get("root", "..")
        project_root = (config_path.parent / root_str).resolve()
        
        # Componentes
        comp_data = data.get("components", {})
        
        kernel = KernelConfig(**comp_data.get("kernel", {}))
        bootloader = BootloaderConfig(**comp_data.get("bootloader", {}))
        
        services = []
        for svc in comp_data.get("services", []):
            services.append(ServiceConfig(**svc))
        
        components = ComponentsConfig(
            kernel=kernel,
            bootloader=bootloader,
            services=services,
        )
        
        # QEMU
        qemu_data = data.get("qemu", {})
        logging_data = qemu_data.pop("logging", {})
        qemu_logging = QemuLoggingConfig(**logging_data)
        qemu = QemuConfig(**qemu_data, logging=qemu_logging)
        
        # Análise
        analysis_data = data.get("analysis", {})
        patterns_data = analysis_data.pop("patterns", [])
        patterns = [PatternConfig(**p) for p in patterns_data]
        analysis = AnalysisConfig(**analysis_data, patterns=patterns)
        
        return cls(
            project_name=project_data.get("name", "RedstoneOS"),
            project_root=project_root,
            components=components,
            qemu=qemu,
            analysis=analysis,
        )


def load_config(config_path: Path | None = None) -> AnvilConfig:
    """
    Carrega configuração do arquivo TOML.
    
    Se não especificado, procura anvil.toml no diretório atual e pai.
    """
    if config_path is None:
        # Procurar anvil.toml
        search_paths = [
            Path.cwd() / "anvil.toml",
            Path.cwd().parent / "anvil" / "anvil.toml",
            Path(__file__).parent.parent.parent / "anvil.toml",
        ]
        
        for path in search_paths:
            if path.exists():
                config_path = path
                break
        else:
            raise ConfigError(
                "Arquivo anvil.toml não encontrado. "
                f"Procurado em: {[str(p) for p in search_paths]}"
            )
    
    if not config_path.exists():
        raise ConfigError(f"Arquivo de configuração não encontrado: {config_path}")
    
    try:
        data = toml.load(config_path)
        return AnvilConfig.from_dict(data, config_path)
    except toml.TomlDecodeError as e:
        raise ConfigError(f"Erro ao parsear {config_path}: {e}")
