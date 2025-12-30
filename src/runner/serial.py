import asyncio
from core.logger import log, console


class PipeSerialListener:
    """
    Escuta logs de um Named Pipe no Windows (ex: VirtualBox).
    """
    
    def __init__(self, pipe_path: str):
        self.pipe_path = pipe_path
        self._stop_event = asyncio.Event()

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
                    # Imprimir preservando formatação (Rich lida com threads se console for global)
                    console.print(text, end="")
        except FileNotFoundError:
            # Pipe ainda não existe, aguardar em silêncio
            pass
        except Exception as e:
            if not self._stop_event.is_set():
                raise e

    def stop(self):
        """Para a escuta."""
        self._stop_event.set()
