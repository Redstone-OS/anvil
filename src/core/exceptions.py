"""
Anvil Core - Exceções customizadas
"""


class AnvilError(Exception):
    """Exceção base do Anvil."""
    pass


class BuildError(AnvilError):
    """Erro durante o build."""
    
    def __init__(self, message: str, component: str | None = None, errors: list[str] | None = None):
        super().__init__(message)
        self.component = component
        self.errors = errors or []


class RunError(AnvilError):
    """Erro durante a execução do QEMU."""
    
    def __init__(self, message: str, exit_code: int | None = None):
        super().__init__(message)
        self.exit_code = exit_code


class AnalysisError(AnvilError):
    """Erro durante análise de logs/binários."""
    pass


class ConfigError(AnvilError):
    """Erro na configuração."""
    pass


class ValidationError(AnvilError):
    """Erro na validação de artefatos."""
    
    def __init__(self, message: str, artifact: str | None = None):
        super().__init__(message)
        self.artifact = artifact
