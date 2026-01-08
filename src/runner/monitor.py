"""Anvil Runner - Monitor QEMU.

Monitora a execução do QEMU em tempo real, detectando exceções de CPU
e gerenciando o ciclo de vida do processo.
"""

import asyncio
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable

from core.config import Config
from core.paths import Paths
from core.logger import Logger, get_logger
from runner.qemu import QemuRunner
from runner.streams import StreamCapture, LogEntry, StreamSource
from runner.serial import SerialColorizer

@dataclass
class CrashInfo:
    """Informações sobre um crash detectado."""
    timestamp: datetime
    exception_type: str
    exception_code: str
    context_lines: list
    rip: Optional[str] = None
    cr2: Optional[str] = None
    rsp: Optional[str] = None

@dataclass
class MonitorResult:
    """Resultado da execução monitorada."""
    success: bool
    runtime_ms: int
    crashed: bool = False
    crash_info: Optional[CrashInfo] = None
    all_crashes: list = field(default_factory=list)
    total_lines: int = 0

class QemuMonitor:
    """Monitor de execução do QEMU."""
    
    # Mapa de exceções x86 conhecidas
    EXCEPTIONS = {
        "v=00": ("Erro de Divisão", "#DE"),
        "v=06": ("Opcode Inválido", "#UD"),
        "v=08": ("Double Fault", "#DF"),
        "v=0d": ("Proteção Geral", "#GP"),
        "v=0e": ("Page Fault", "#PF"),
    }
    
    def __init__(self, paths, config, log=None, stop_on_exception=True, show_serial=True, on_exception=None):
        self.paths = paths
        self.config = config
        self.log = log or get_logger()
        self.stop_on_exception = stop_on_exception
        self.show_serial = show_serial
        self.on_exception = on_exception
        self.runner = QemuRunner(paths, config, log)
        self.capture = StreamCapture()
        self._crash_info = None
        self._all_crashes = []
        self._last_rip = None
        self._should_stop = False
        
    def _on_entry(self, entry):
        """Callback chamado para cada nova linha de log."""
        
        # O StreamCapture lê tudo do stdout do QEMU como "SERIAL".
        # Porém, como usamos '2>&1', logs de debug do QEMU (-d int,cpu...) também vêm por aqui.
        # Precisamos filtrar para mostrar APENAS o que parece ser serial do SO (ANSI color formatado ou texto limpo)
        # Logs de CPU geralmente começam com códigos hex ou abreviações específicas (EAX=, Servicing, etc)
        # O User quer apenas o que o SerialColorizer processa ou o que foi limpo.
        
        if self.show_serial and entry.source == StreamSource.SERIAL:
            # O output agora deve vir limpo do QEMU/WSL (Debug -> /dev/null)
            # Apenas aplicamos cores
            colored = SerialColorizer.colorize(entry.line)
            if colored.strip():
                self.log.raw(colored)

        # Rastreia RIP para contexto de crash (fallback se passou pelo filtro visual)
        if entry.line.startswith("RIP="): self._last_rip = entry.line.split()[0]
        
        # Verifica se é uma exceção
        crash = self._detect_exception(entry)
        if crash:
            # Pequeno delay para capturar contexto extra
            time.sleep(0.5)
            self._crash_info = crash
            self._all_crashes.append(crash)
            if self.on_exception: self.on_exception(crash)
            if self.stop_on_exception: self._should_stop = True
            
    def _detect_exception(self, entry):
        """Analisa a linha procurando por padrões de exceção x86."""
        line = entry.line
        for pattern, (name, code) in self.EXCEPTIONS.items():
            if pattern in line or "check_exception" in line:
                # Extrai registradores importantes se disponíveis
                cr2 = None
                if "v=0e" in line: # Page Fault tem endereço no CR2
                    match = re.search(r"CR2=([0-9a-fA-Fx]+)", line)
                    if match: cr2 = match.group(1)
                    
                rsp = None
                rsp_match = re.search(r"RSP=([0-9a-fA-Fx]+)", line)
                if rsp_match: rsp = rsp_match.group(1)
                
                return CrashInfo(
                    entry.timestamp, name, code,
                    self.capture.get_context(100), self._last_rip, cr2, rsp
                )
        return None
        
    async def run_monitored(self, timeout=None):
        """Executa o QEMU monitorando logs e serial."""
        start = time.time()
        self._crash_info = None
        self._all_crashes = []
        self._should_stop = False
        self._last_rip = None
        
        # Registra nosso listener
        self.capture.add_callback(self._on_entry)
        
        try:
            process = await self.runner.start()
            if not process.stdout: return MonitorResult(False, 0, True)
            
            # Tasks para capturar output
            serial_task = asyncio.create_task(self.capture.capture_serial(process.stdout))
            # CPU Log removido a pedido
            # cpu_task = asyncio.create_task(self.capture.capture_cpu_log(self.paths.cpu_log))
            
            exit_task = asyncio.create_task(process.wait())
            
            # Loop de monitoramento
            while True:
                if self._should_stop:
                    try: process.terminate(); await process.wait()
                    except: pass
                    break
                
                if exit_task.done(): break
                
                if timeout and (time.time() - start) > timeout:
                    try: process.terminate()
                    except: pass
                    break
                    
                await asyncio.sleep(0.1)
                
            self.capture.stop()
            try: await serial_task
            except: pass
            
            # Logs já são salvos pelo comando bash (tee -> file)
            # self._save_logs()
            
            return MonitorResult(
                success=not self._crash_info, 
                runtime_ms=int((time.time()-start)*1000), 
                crashed=self._crash_info is not None, 
                crash_info=self._crash_info, 
                all_crashes=self._all_crashes, 
                total_lines=self.capture.total_lines
            )
        except Exception as e:
            self.log.error(f"Erro: {e}"); await self.runner.stop()
            return MonitorResult(False, int((time.time()-start)*1000), True)
            
    def _save_logs(self):
        """Salva logs da sessão na pasta de logs do Anvil."""
        try:
            log_dir = self.paths.anvil_log_dir
            log_dir.mkdir(parents=True, exist_ok=True)
            
            serial_entries = self.capture.get_serial(10000)
            cpu_entries = self.capture.get_cpu(10000)
            
            (log_dir / "serial.log").write_text("\n".join(e.line for e in serial_entries), encoding="utf-8")
            (log_dir / "cpu.log").write_text("\n".join(e.line for e in cpu_entries), encoding="utf-8")
        except: pass
