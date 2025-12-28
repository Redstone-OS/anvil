"""
Anvil Core - Logging estruturado com Rich
"""

from rich.console import Console
from rich.theme import Theme
from rich.logging import RichHandler
import logging

# Tema customizado do Anvil
ANVIL_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red bold",
    "success": "green",
    "debug": "dim",
    "header": "cyan bold",
    "path": "blue underline",
    "component": "magenta",
})

# Console global
console = Console(theme=ANVIL_THEME)


def setup_logging(verbose: bool = False, debug: bool = False) -> None:
    """Configura logging global com Rich."""
    level = logging.DEBUG if debug else (logging.INFO if verbose else logging.WARNING)
    
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


class AnvilLogger:
    """Logger estruturado para o Anvil."""
    
    def __init__(self, name: str = "anvil"):
        self._logger = logging.getLogger(name)
    
    def header(self, title: str) -> None:
        """Imprime cabeçalho de seção."""
        console.print()
        console.print("=" * 50, style="cyan")
        console.print(f"   {title}", style="header")
        console.print("=" * 50, style="cyan")
    
    def info(self, message: str, **kwargs) -> None:
        """Log informativo."""
        console.print(f"[info]ℹ️  {message}[/info]", **kwargs)
    
    def success(self, message: str, **kwargs) -> None:
        """Log de sucesso."""
        console.print(f"[success]✓ {message}[/success]", **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log de aviso."""
        console.print(f"[warning]⚠️  {message}[/warning]", **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log de erro."""
        console.print(f"[error]✗ {message}[/error]", **kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log de debug."""
        console.print(f"[debug]🔍 {message}[/debug]", **kwargs)
    
    def step(self, message: str, **kwargs) -> None:
        """Log de passo do processo."""
        console.print(f"  → {message}", style="dim", **kwargs)
    
    def component(self, name: str, status: str, success: bool = True) -> None:
        """Log de status de componente."""
        icon = "✓" if success else "✗"
        style = "success" if success else "error"
        console.print(f"  [{style}]{icon}[/{style}] [component]{name}[/component]: {status}")


# Logger global
log = AnvilLogger()
