import asyncio
import re
from core.logger import log, console


def colorize_line(line: str) -> str:
    """Aplica cores às tags conhecidas e remove ANSI codes antigos."""
    # Remover códigos ANSI existentes (escape sequences)
    ansi_escape = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]')
    line = ansi_escape.sub('', line)
    
    # Colorir tags conhecidas
    line = re.sub(r'\[OK\]', '[green][OK][/green]', line)
    line = re.sub(r'\[FAIL\]', '[red bold][FAIL][/red bold]', line)
    line = re.sub(r'\[JUMP\]', '[magenta][JUMP][/magenta]', line)
    line = re.sub(r'\[TRACE\]', '[purple][TRACE][/purple]', line)
    line = re.sub(r'\[DEBUG\]', '[dim][DEBUG][/dim]', line)
    line = re.sub(r'\[INFO\]', '[cyan][INFO][/cyan]', line)
    line = re.sub(r'\[WARN\]', '[yellow][WARN][/yellow]', line)
    line = re.sub(r'\[ERROR\]', '[red][ERROR][/red]', line)
    
    return line


class PipeSerialListener:
    """
    Escuta logs de um Named Pipe no Windows (ex: VirtualBox).
    """
    
    def __init__(self, pipe_path: str):
        self.pipe_path = pipe_path
        self._stop_event = asyncio.Event()
        self._buffer = ""

    async def start(self):
        """Inicia a escuta no pipe."""
        log.header(f"Pipe Serial: {self.pipe_path}")
        
        while not self._stop_event.is_set():
            try:
                # Usar run_in_executor para não travar o loop de eventos na abertura/leitura do pipe
                await asyncio.get_event_loop().run_in_executor(None, self._read_pipe)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._stop_event.is_set():
                    log.error(f"Erro no pipe: {e}")
                    await asyncio.sleep(2)

    def _read_pipe(self):
        try:
            # No Windows, pipes podem ser abertos como arquivos binários para leitura
            with open(self.pipe_path, "rb") as f:
                log.success(f"Conectado ao pipe: {self.pipe_path}")
                while not self._stop_event.is_set():
                    # Leitura em blocos de 1KB
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    
                    text = chunk.decode("utf-8", errors="replace")
                    
                    # Processar linha por linha para aplicar cores corretamente
                    self._buffer += text
                    if "\n" in self._buffer:
                        lines = self._buffer.split("\n")
                        # A última parte pode estar incompleta
                        self._buffer = lines.pop()
                        
                        for line in lines:
                            colored = colorize_line(line)
                            console.print(colored)
                            
        except FileNotFoundError:
            # Pipe ainda não existe, aguardar em silêncio
            pass
        except Exception as e:
            if not self._stop_event.is_set():
                raise e

    def stop(self):
        """Para a escuta."""
        self._stop_event.set()
