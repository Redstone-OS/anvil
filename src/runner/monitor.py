"""Anvil Runner - Real-time QEMU monitoring."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from core.config import Config
from core.paths import Paths
from core.logger import Logger, get_logger
from runner.qemu import QemuRunner, QemuConfig
from runner.streams import StreamCapture, LogEntry, StreamSource
from runner.serial import SerialColorizer


@dataclass
class CrashInfo:
    """Information about a detected crash."""
    timestamp: datetime
    exception_type: str
    exception_code: str
    context_lines: list[LogEntry]
    rip: Optional[str] = None
    cr2: Optional[str] = None
    rsp: Optional[str] = None
    
    def __str__(self) -> str:
        return f"{self.exception_type} ({self.exception_code}) @ RIP={self.rip or 'unknown'}"


@dataclass
class MonitorResult:
    """Result of monitored QEMU execution."""
    success: bool
    runtime_ms: int
    crashed: bool = False
    crash_info: Optional[CrashInfo] = None
    all_crashes: list[CrashInfo] = field(default_factory=list)
    total_lines: int = 0


class QemuMonitor:
    """Real-time QEMU monitor with crash detection."""
    
    EXCEPTIONS = {
        "v=00": ("Divide Error", "#DE"),
        "v=06": ("Invalid Opcode", "#UD"),
        "v=08": ("Double Fault", "#DF"),
        "v=0d": ("General Protection", "#GP"),
        "v=0e": ("Page Fault", "#PF"),
    }
    
    def __init__(
        self,
        paths: Paths,
        config: Config,
        log: Optional[Logger] = None,
        stop_on_exception: bool = True,
        show_serial: bool = True,
        on_exception: Optional[Callable[[CrashInfo], None]] = None,
    ):
        self.paths = paths
        self.config = config
        self.log = log or get_logger()
        self.stop_on_exception = stop_on_exception
        self.show_serial = show_serial
        self.on_exception = on_exception
        
        self.runner = QemuRunner(paths, config, log)
        self.capture = StreamCapture()
        
        self._crash_info: Optional[CrashInfo] = None
        self._all_crashes: list[CrashInfo] = []
        self._last_rip: Optional[str] = None
        self._should_stop = False
    
    def _on_entry(self, entry: LogEntry) -> None:
        if self.show_serial and entry.source == StreamSource.SERIAL:
            colored = SerialColorizer.colorize(entry.line)
            self.log.raw(colored)
        
        if entry.line.startswith("RIP="):
            self._last_rip = entry.line.split()[0]
        
        crash = self._detect_exception(entry)
        if crash:
            time.sleep(0.5)
            self._crash_info = crash
            self._all_crashes.append(crash)
            if self.on_exception: self.on_exception(crash)
            if self.stop_on_exception: self._should_stop = True
    
    def _detect_exception(self, entry: LogEntry) -> Optional[CrashInfo]:
        line = entry.line
        for pattern, (name, code) in self.EXCEPTIONS.items():
            if pattern in line or "check_exception" in line:
                cr2 = None
                if "v=0e" in line:
                    match = re.search(r"CR2=([0-9a-fA-Fx]+)", line)
                    if match: cr2 = match.group(1)
                rsp = None
                rsp_match = re.search(r"RSP=([0-9a-fA-Fx]+)", line)
                if rsp_match: rsp = rsp_match.group(1)
                
                return CrashInfo(
                    timestamp=entry.timestamp, exception_type=name, exception_code=code,
                    context_lines=self.capture.get_context(100), rip=self._last_rip,
                    cr2=cr2, rsp=rsp,
                )
        return None
    
    async def run_monitored(self, qemu_config: Optional[QemuConfig] = None, timeout: Optional[float] = None) -> MonitorResult:
        start = time.time()
        self._crash_info = None
        self._all_crashes = []
        self._should_stop = False
        self._last_rip = None
        self.capture.add_callback(self._on_entry)
        try:
            process = await self.runner.start(qemu_config)
            if not process.stdout: return MonitorResult(False, 0, True)
            serial_task = asyncio.create_task(self.capture.capture_serial(process.stdout))
            cpu_task = asyncio.create_task(self.capture.capture_cpu_log(self.paths.cpu_log))
            exit_task = asyncio.create_task(process.wait())
            
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
            for task in [serial_task, cpu_task]:
                task.cancel()
                try: await task
                except asyncio.CancelledError: pass
            
            runtime_ms = int((time.time() - start) * 1000)
            self._save_logs()
            return MonitorResult(not self._crash_info, runtime_ms, self._crash_info is not None, self._crash_info, self._all_crashes, self.capture.total_lines)
        except Exception as e:
            self.log.error(f"Error: {e}"); await self.runner.stop()
            return MonitorResult(False, int((time.time() - start) * 1000), True)
    
    def _save_logs(self) -> None:
        try:
            log_dir = self.paths.anvil_log_dir
            log_dir.mkdir(parents=True, exist_ok=True)
            serial_file = log_dir / "serial.log"
            cpu_file = log_dir / "cpu.log"
            serial_entries = self.capture.get_serial(lines=10000)
            cpu_entries = self.capture.get_cpu(lines=10000)
            serial_file.write_text("\n".join(e.line for e in serial_entries), encoding="utf-8")
            cpu_file.write_text("\n".join(e.line for e in cpu_entries), encoding="utf-8")
        except: pass

    def get_context(self, lines: int = 50) -> list[LogEntry]:
        return self.capture.get_context(lines)
