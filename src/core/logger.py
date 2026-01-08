"""Anvil Core - Logger Simples com cores ANSI.

Este módulo fornece uma classe Logger básica para imprimir mensagens coloridas
no terminal, substituindo a antiga dependência 'rich' por sequências de escape ANSI.
"""

import sys
from datetime import datetime
from enum import Enum

class LogLevel(Enum):
    """Níveis de severidade do log."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARN"
    ERROR = "ERROR"

class Colors:
    """Definições de códigos de escape ANSI para cores."""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GREY = "\033[90m"
    BOLD = "\033[1m"

class Logger:
    """
    Logger simples que escreve no stdout com cores.
    Suporta níveis de log como info, success, warning, error e debug.
    """
    
    def __init__(self, name="anvil", verbose=False):
        self.name = name
        self.verbose = verbose

    def _print(self, level_color, box_char, message):
        """Método interno para formatar e imprimir a mensagem de log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        # Formato: HH:MM:SS [X] Mensagem
        print(f"{Colors.GREY}{timestamp}{Colors.RESET} {level_color}{box_char}{Colors.RESET} {message}")

    def header(self, title):
        """Imprime um cabeçalho de seção."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}=== {title} ==={Colors.RESET}")

    def info(self, message):
        """Log de informação geral (Azul 'i')."""
        self._print(Colors.BLUE, "i", message)

    def success(self, message):
        """Log de sucesso (Verde '✓')."""
        self._print(Colors.GREEN, "✓", message)

    def warning(self, message):
        """Log de aviso (Amarelo '!')."""
        self._print(Colors.YELLOW, "!", message)

    def error(self, message):
        """Log de erro (Vermelho 'x')."""
        self._print(Colors.RED, "x", message)

    def debug(self, message):
        """Log de debug (Cinza '?'), visível apenas se verbose=True."""
        if self.verbose:
            self._print(Colors.GREY, "?", message)

    def step(self, message):
        """Log de passo de execução (seta cinza)."""
        print(f"   {Colors.GREY}→ {message}{Colors.RESET}")

    def raw(self, message):
        """Imprime a mensagem exatamente como recebida, sem formatação extra."""
        print(message, flush=True)

# Instância global do logger
_logger = None

def get_logger(name="anvil", verbose=False, console=None):
    """
    Retorna a instância global do logger (Singleton).
    O argumento 'console' é mantido para compatibilidade, mas ignorado.
    """
    global _logger
    if _logger is None:
        _logger = Logger(name, verbose)
    return _logger
