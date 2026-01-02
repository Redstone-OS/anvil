"""Anvil Core - Execution context container."""

from __future__ import annotations

from dataclasses import dataclass

from core.config import Config, load_config
from core.paths import Paths
from core.logger import Logger, get_logger


@dataclass
class Context:
    """
    Shared execution context.
    
    Groups all dependencies needed by commands:
    - Configuration from toml
    - Path resolver
    - Logger instance
    
    This avoids passing multiple arguments everywhere.
    """
    config: Config
    paths: Paths
    log: Logger
    
    @classmethod
    def create(cls, verbose: bool = False) -> Context:
        """Create context with auto-detected configuration."""
        config = load_config()
        paths = Paths(config.project_root)
        log = get_logger(verbose=verbose)
        
        return cls(config=config, paths=paths, log=log)
    
    def ensure_dirs(self) -> None:
        """Ensure all required directories exist."""
        self.paths.ensure_dirs()

