"""Anvil Core - Structured logging with Rich."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, Any

from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.logging import RichHandler


class LogLevel(Enum):
    """Log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


# Anvil color theme
THEME = Theme({
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "bold red",
    "debug": "dim",
    "header": "bold cyan",
    "accent": "#ffa500",  # Orange
    "muted": "#808080",
    "path": "blue underline",
})


@dataclass
class LogEntry:
    """Single log entry."""
    timestamp: datetime
    level: LogLevel
    message: str
    source: Optional[str] = None


class Logger:
    """
    Structured logger with Rich formatting.
    
    Supports:
    - Console output with colors
    - TUI redirection via callbacks
    - File logging
    """
    
    def __init__(
        self,
        name: str = "anvil",
        console: Optional[Console] = None,
        verbose: bool = False,
    ):
        self.name = name
        self.console = console or Console(theme=THEME)
        self.verbose = verbose
        self._callbacks: list[Callable[[LogEntry], None]] = []
        
        # Setup Python logging integration
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configure standard Python logging."""
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format="%(message)s",
            handlers=[RichHandler(console=self.console, rich_tracebacks=True)],
        )
    
    def add_callback(self, callback: Callable[[LogEntry], None]) -> None:
        """Add callback for log entries (used by TUI)."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[LogEntry], None]) -> None:
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _emit(self, level: LogLevel, message: str, **kwargs: Any) -> None:
        """Internal: emit log entry."""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            message=message,
            source=kwargs.get("source"),
        )
        
        for callback in self._callbacks:
            try:
                callback(entry)
            except Exception:
                pass  # Don't let callback errors break logging
    
    # =========================================================================
    # Public API
    # =========================================================================
    
    def header(self, title: str) -> None:
        """Print section header."""
        self.console.print()
        self.console.print(f"[bold accent]{'━' * 50}[/]")
        self.console.print(f"[bold accent]   {title}[/]")
        self.console.print(f"[bold accent]{'━' * 50}[/]")
        self._emit(LogLevel.INFO, title)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log informational message."""
        self.console.print(f"[info]ℹ  {message}[/]")
        self._emit(LogLevel.INFO, message, **kwargs)
    
    def success(self, message: str, **kwargs: Any) -> None:
        """Log success message."""
        self.console.print(f"[success]✓  {message}[/]")
        self._emit(LogLevel.SUCCESS, message, **kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self.console.print(f"[warning]⚠  {message}[/]")
        self._emit(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self.console.print(f"[error]✗  {message}[/]")
        self._emit(LogLevel.ERROR, message, **kwargs)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message (only if verbose)."""
        if self.verbose:
            self.console.print(f"[debug]🔍 {message}[/]")
            self._emit(LogLevel.DEBUG, message, **kwargs)
    
    def step(self, message: str, **kwargs: Any) -> None:
        """Log process step."""
        self.console.print(f"[muted]   → {message}[/]")
        self._emit(LogLevel.INFO, message, **kwargs)
    
    def component(self, name: str, status: str, success: bool = True) -> None:
        """Log component build status."""
        icon = "✓" if success else "✗"
        color = "success" if success else "error"
        self.console.print(f"   [{color}]{icon}[/] [bold]{name}[/]: {status}")
        self._emit(
            LogLevel.SUCCESS if success else LogLevel.ERROR,
            f"{name}: {status}",
        )
    
    def raw(self, message: str) -> None:
        """Print raw message without formatting."""
        self.console.print(message)
    
    def print(self, *args: Any, **kwargs: Any) -> None:
        """Proxy to console.print for compatibility."""
        self.console.print(*args, **kwargs)


# Global logger instance
_default_logger: Optional[Logger] = None


def get_logger(
    name: str = "anvil",
    verbose: bool = False,
    console: Optional[Console] = None,
) -> Logger:
    """Get or create the global logger instance."""
    global _default_logger
    
    if _default_logger is None:
        _default_logger = Logger(name=name, verbose=verbose, console=console)
    
    return _default_logger


def reset_logger() -> None:
    """Reset the global logger (used in tests)."""
    global _default_logger
    _default_logger = None

