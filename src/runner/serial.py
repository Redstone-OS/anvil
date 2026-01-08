"""Anvil Runner - Colorização de saída Serial.

Este módulo lida com a leitura de named pipes do Windows para capturar
a saída serial do QEMU e aplicar cores para melhorar a legibilidade.
Também remove caracteres de controle ANSI indesejados gerados pelo UEFI/Kernel.
"""

import asyncio
import re

class Colors:
    """Códigos de cor ANSI para o terminal."""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GREY = "\033[90m"

class SerialColorizer:
    """Classe utilitária para colorir logs seriais brutos."""
    
    # Remove códigos ANSI complexos vindos do guest (ex: logs do EDK2)
    ANSI_CLEANER = re.compile(r"\x1b\[[0-9;?]*[A-Za-z=]")
    
    # Padrões de substituição: (Regex, Cor ANSI)
    PATTERNS = [
        (r"\[OK\]", f"{Colors.GREEN}[OK]{Colors.RESET}"),
        (r"\[FAIL\]", f"{Colors.RED}[FAIL]{Colors.RESET}"),
        (r"\[ERROR\]", f"{Colors.RED}[ERROR]{Colors.RESET}"),
        (r"\[WARN\]", f"{Colors.RED}[WARN]{Colors.RESET}"),
        (r"\[TRACE\]", f"{Colors.MAGENTA}[TRACE]{Colors.RESET}"),
        (r"\[DEBUG\]", f"{Colors.GREY}[DEBUG]{Colors.RESET}"),
        (r"\[INFO\]", f"{Colors.CYAN}[INFO]{Colors.RESET}"),
        (r"\[Supervisor\]", f"{Colors.YELLOW}[Supervisor]{Colors.RESET}"),
        (r"\[Compositor\]", f"{Colors.BLUE}[Compositor]{Colors.RESET}"),
        (r"\[Shell\]", f"{Colors.GREEN}[Shell]{Colors.RESET}"),
        (r"\[Input\]", f"{Colors.MAGENTA}[Input]{Colors.RESET}"),
    ]

    @classmethod
    def colorize(cls, line: str) -> str:
        """Processa uma linha de texto, limpando e colorindo."""
        
        # 1. Limpeza: Remove códigos de escape existentes para evitar conflitos
        line = cls.ANSI_CLEANER.sub("", line)
        
        # 2. Filtragem: Mantém apenas caracteres ASCII imprimíveis, newline e return
        # Isso remove lixo binário ou caracteres estranhos que aparecem no boot
        line = "".join(ch for ch in line if 32 <= ord(ch) <= 126 or ch == '\n' or ch == '\r')
        
        if not line.strip():
            return ""

        # FILTRO EXPLICITO DE CPU LOGS
        # Remove linhas que parecem dump de registradores ou interrupções do QEMU
        if "RAX=" in line or "EAX=" in line or "CR3=" in line or "Servicing" in line:
            return ""

        # 3. Aplicação de padrões de tags (ex: [OK], [ERROR])
        for pattern, replacement in cls.PATTERNS:
            line = re.sub(pattern, replacement, line)
        
        # 4. Realces sintáticos simples
        
        # 'texto entre aspas' -> verde
        line = re.sub(r"(?<!\[)'([^'\]]+)'(?!\[)", f"{Colors.GREEN}'\\1'{Colors.RESET}", line)
        
        # (texto em parenteses) -> ciano
        line = re.sub(r"(?<!\[)\(([a-zA-Z0-9_ ]+)\)(?![\w\]])", f"{Colors.CYAN}(\\1){Colors.RESET}", line)
        
        # funcao() -> ciano
        line = re.sub(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\(\)", f"{Colors.CYAN}\\1(){Colors.RESET}", line)
        
        # 0xHEX -> amarelo
        line = re.sub(r"\b(0x[0-9a-fA-F]+)\b", f"{Colors.YELLOW}\\1{Colors.RESET}", line)
        
        # números -> amarelo
        line = re.sub(r"(?<![a-zA-Z#\[])\b(\d+(?:\.\d+)?)\b(?![a-zA-Z])", f"{Colors.YELLOW}\\1{Colors.RESET}", line)
        
        return line

class PipeListener:
    """Ouve a saída serial através de um Named Pipe do Windows (usado pelo QEMU/VirtBox)."""
    
    def __init__(self, pipe_path=r"\\.\pipe\VBoxCom1", on_line=None):
        self.pipe_path = pipe_path
        self.on_line = on_line
        self._stop_event = asyncio.Event()
        self._buffer = ""

    async def start(self):
        """Inicia a escuta em background."""
        asyncio.create_task(self._run_loop())

    async def _run_loop(self):
        """Loop principal que tenta conectar ao pipe."""
        while not self._stop_event.is_set():
            try:
                # Executa a leitura bloqueante em um executor para não travar o async
                await asyncio.get_event_loop().run_in_executor(None, self._read_pipe)
            except Exception:
                # Se falhar (pipe não existe ainda), espera um pouco e tenta de novo
                await asyncio.sleep(1)

    def _read_pipe(self):
        """Lê do pipe de forma síncrona."""
        try:
            with open(self.pipe_path, "rb") as f:
                print(f"{Colors.GREEN}Serial Conectado{Colors.RESET}")
                while not self._stop_event.is_set():
                    chunk = f.read(1024)
                    if not chunk: break
                    
                    text = chunk.decode("utf-8", errors="replace")
                    self._buffer += text
                    
                    # Processa linha por linha
                    if "\n" in self._buffer:
                        lines = self._buffer.split("\n")
                        self._buffer = lines.pop() # Guarda o resto que não formou linha completa
                        
                        for line in lines:
                            out = SerialColorizer.colorize(line)
                            if out and self.on_line: self.on_line(out)
        except Exception:
            pass

    def stop(self):
        """Para a escuta."""
        self._stop_event.set()
