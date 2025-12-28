"""
Anvil Runner - Monitor de execução QEMU em tempo real
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Any

from core.config import AnvilConfig
from core.logger import log, console
from core.paths import PathResolver
from runner.qemu import QemuRunner, QemuConfig
from runner.streams import DualStreamCapture, LogEntry, StreamSource


@dataclass
class CrashInfo:
    """Informação sobre crash detectado."""
    timestamp: datetime
    exception_type: str
    exception_code: str
    context_lines: list[LogEntry]
    rip: Optional[str] = None
    cr2: Optional[str] = None
    
    def __str__(self) -> str:
        return f"{self.exception_type} ({self.exception_code}) @ RIP={self.rip or 'unknown'}"


@dataclass
class MonitorResult:
    """Resultado do monitoramento."""
    success: bool
    runtime_ms: int
    crashed: bool = False
    crash_info: Optional[CrashInfo] = None
    total_lines: int = 0
    
    
class QemuMonitor:
    """
    Monitor de execução QEMU em tempo real.
    
    Captura simultaneamente:
    - stdout/stderr (serial via -serial stdio)
    - Log interno QEMU (-D arquivo.log)
    
    Detecta erros e pode parar execução automaticamente.
    """
    
    # Padrões de exceção
    EXCEPTION_PATTERNS = {
        "v=00": ("Divide Error", "#DE"),
        "v=06": ("Invalid Opcode", "#UD"),
        "v=08": ("Double Fault", "#DF"),
        "v=0d": ("General Protection", "#GP"),
        "v=0e": ("Page Fault", "#PF"),
    }
    
    def __init__(
        self,
        paths: PathResolver,
        config: AnvilConfig,
        on_exception: Optional[Callable[[CrashInfo], None]] = None,
        stop_on_exception: bool = True,
    ):
        self.paths = paths
        self.config = config
        self.on_exception = on_exception
        self.stop_on_exception = stop_on_exception
        
        self.runner = QemuRunner(paths, config)
        self.capture = DualStreamCapture()
        self._crash_info: Optional[CrashInfo] = None
        self._last_rip: Optional[str] = None
        self._should_stop = False
    
    def _detect_exception(self, entry: LogEntry) -> Optional[CrashInfo]:
        """Detecta exceção de CPU na linha."""
        line = entry.line
        
        # Capturar RIP
        if line.startswith("RIP="):
            self._last_rip = line.split()[0]
        
        # Detectar exceção
        for pattern, (name, code) in self.EXCEPTION_PATTERNS.items():
            if pattern in line or "check_exception" in line:
                # Extrair CR2 se page fault
                cr2 = None
                if "v=0e" in line:
                    import re
                    match = re.search(r"CR2=([0-9a-fA-Fx]+)", line)
                    if match:
                        cr2 = match.group(1)
                
                return CrashInfo(
                    timestamp=entry.timestamp,
                    exception_type=name,
                    exception_code=code,
                    context_lines=self.capture.get_context(50),
                    rip=self._last_rip,
                    cr2=cr2,
                )
        
        return None
    
    def _on_log_entry(self, entry: LogEntry) -> None:
        """Callback para cada linha de log."""
        # Detectar exceção
        crash = self._detect_exception(entry)
        
        if crash:
            self._crash_info = crash
            console.print(f"\n[red bold]💥 EXCEÇÃO DETECTADA: {crash}[/red bold]")
            
            if self.on_exception:
                self.on_exception(crash)
            
            if self.stop_on_exception:
                self._should_stop = True
    
    async def run_monitored(
        self,
        qemu_config: Optional[QemuConfig] = None,
        timeout: Optional[float] = None,
    ) -> MonitorResult:
        """
        Executa QEMU com monitoramento completo.
        
        1. Inicia QEMU via WSL
        2. Cria tasks assíncronos para cada stream
        3. Alimenta análise em tempo real
        4. Detecta erros e para execução se configurado
        """
        import time
        start_time = time.time()
        
        # Registrar callback
        self.capture.add_callback(self._on_log_entry)
        
        try:
            # Iniciar QEMU
            process = await self.runner.run(qemu_config)
            
            if not process.stdout:
                return MonitorResult(
                    success=False,
                    runtime_ms=0,
                    crashed=True,
                )
            
            # Iniciar captura de streams
            serial_task = asyncio.create_task(
                self.capture.capture_serial(process.stdout)
            )
            
            cpu_log_task = asyncio.create_task(
                self.capture.capture_cpu_log(self.paths.internal_log)
            )
            
            # Loop principal
            while True:
                # Verificar se deve parar
                if self._should_stop:
                    log.warning("Parando QEMU devido a exceção detectada")
                    await self.runner.stop()
                    break
                
                # Verificar se processo terminou
                if process.returncode is not None:
                    break
                
                # Timeout
                elapsed = time.time() - start_time
                if timeout and elapsed > timeout:
                    log.warning(f"Timeout após {timeout}s")
                    await self.runner.stop()
                    break
                
                await asyncio.sleep(0.1)
            
            # Parar captura
            self.capture.stop()
            
            # Aguardar tasks
            serial_task.cancel()
            cpu_log_task.cancel()
            
            try:
                await serial_task
            except asyncio.CancelledError:
                pass
            
            try:
                await cpu_log_task
            except asyncio.CancelledError:
                pass
            
            runtime_ms = int((time.time() - start_time) * 1000)
            
            return MonitorResult(
                success=not self._crash_info,
                runtime_ms=runtime_ms,
                crashed=self._crash_info is not None,
                crash_info=self._crash_info,
                total_lines=self.capture.total_lines,
            )
            
        except Exception as e:
            log.error(f"Erro no monitor: {e}")
            await self.runner.stop()
            
            return MonitorResult(
                success=False,
                runtime_ms=int((time.time() - start_time) * 1000),
                crashed=True,
            )
    
    def get_context(self, lines: int = 50) -> list[LogEntry]:
        """Retorna contexto do log."""
        return self.capture.get_context(lines)
