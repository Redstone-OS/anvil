"""Anvil Core - Custom exception hierarchy."""

from dataclasses import dataclass, field
from typing import Optional


class AnvilError(Exception):
    """Base exception for all Anvil errors."""
    
    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message}\n{self.details}"
        return self.message


class ConfigError(AnvilError):
    """Configuration file or parsing error."""
    pass


class BuildError(AnvilError):
    """Build process failure."""
    
    def __init__(
        self,
        message: str,
        component: Optional[str] = None,
        errors: Optional[list[str]] = None,
    ):
        super().__init__(message)
        self.component = component
        self.errors = errors or []
    
    def __str__(self) -> str:
        result = self.message
        if self.component:
            result = f"[{self.component}] {result}"
        if self.errors:
            result += "\n" + "\n".join(f"  - {e}" for e in self.errors[:5])
        return result


class RunError(AnvilError):
    """QEMU execution failure."""
    
    def __init__(
        self,
        message: str,
        exit_code: Optional[int] = None,
        stderr: Optional[str] = None,
    ):
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr


class AnalysisError(AnvilError):
    """Log/binary analysis failure."""
    pass


class ValidationError(AnvilError):
    """Artifact validation failure."""
    
    def __init__(self, message: str, artifact: Optional[str] = None):
        super().__init__(message)
        self.artifact = artifact

