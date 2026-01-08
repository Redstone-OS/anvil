"""Anvil Core - Hierarquia de exceções customizadas."""

from dataclasses import dataclass
from typing import Optional

class AnvilError(Exception):
    """Exceção base para erros do Anvil."""
    
    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details
        
    def __str__(self) -> str:
        if self.details:
            return f"{self.message}\n{self.details}"
        return self.message

class ConfigError(AnvilError):
    """Erro de configuração ou parsing."""
    pass

class BuildError(AnvilError):
    """Falha durante o processo de build."""
    
    def __init__(self, message: str, component: Optional[str] = None, errors: Optional[list[str]] = None):
        super().__init__(message)
        self.component = component
        self.errors = errors or []
        
    def __str__(self) -> str:
        result = self.message
        if self.component:
            result = f"[{self.component}] {result}"
        if self.errors:
            # Lista os primeiros 5 erros específicos se houver
            result += "\n" + "\n".join(f"  - {e}" for e in self.errors[:5])
        return result

class RunError(AnvilError):
    """Falha na execução do QEMU ou processos externos."""
    
    def __init__(self, message: str, exit_code: Optional[int] = None, stderr: Optional[str] = None):
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr

class AnalysisError(AnvilError):
    """Falha na análise de logs ou binários."""
    pass

class ValidationError(AnvilError):
    """Falha na validação de existência de arquivos ou artefatos."""
    
    def __init__(self, message: str, artifact: Optional[str] = None):
        super().__init__(message)
        self.artifact = artifact
