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
    """
    Real-time QEMU monitor with crash detection.
    
    Features:
    - Dual stream capture (serial + CPU log)
    - Exception detection (PF, GP, UD, DF, DE)
    - Automatic stop on crash
    - Rich serial output display
    """
    
    # Exception patterns: vector -> (name, code)
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
        """Callback for each captured log entry."""
        # Show serial output
        if self.show_serial and entry.source == StreamSource.SERIAL:
            colored = SerialColorizer.colorize(entry.line)
            self.log.raw(colored)
        
        # Track RIP
        if entry.line.startswith("RIP="):
            self._last_rip = entry.line.split()[0]
        
        # Detect exception
        crash = self._detect_exception(entry)
        if crash:
            time.sleep(0.5)  # Let more context arrive
            
            self._crash_info = crash
            self._all_crashes.append(crash)
            
            if self.on_exception:
                self.on_exception(crash)
            
            if self.stop_on_exception:
                self._should_stop = True
    
    def _detect_exception(self, entry: LogEntry) -> Optional[CrashInfo]:
        """Check if entry indicates a CPU exception."""
        line = entry.line
        
        for pattern, (name, code) in self.EXCEPTIONS.items():
            if pattern in line or "check_exception" in line:
                # Extract CR2 for page faults
                cr2 = None
                if "v=0e" in line:
                    match = re.search(r"CR2=([0-9a-fA-Fx]+)", line)
                    if match:
                        cr2 = match.group(1)
                
                # Extract RSP
                rsp = None
                rsp_match = re.search(r"RSP=([0-9a-fA-Fx]+)", line)
                if rsp_match:
                    rsp = rsp_match.group(1)
                
                return CrashInfo(
                    timestamp=entry.timestamp,
                    exception_type=name,
                    exception_code=code,
                    context_lines=self.capture.get_context(100),
                    rip=self._last_rip,
                    cr2=cr2,
                    rsp=rsp,
                )
        
        return None
    
    async def run_monitored(
        self,
        qemu_config: Optional[QemuConfig] = None,
        timeout: Optional[float] = None,
    ) -> MonitorResult:
        """
        Run QEMU with full monitoring.
        
        Args:
            qemu_config: QEMU configuration (uses defaults if None)
            timeout: Maximum runtime in seconds
        
        Returns:
            MonitorResult with crash info and statistics
        """
        start = time.time()
        
        # Setup callback
        self.capture.add_callback(self._on_entry)
        
        try:
            # Start QEMU
            process = await self.runner.start(qemu_config)
            
            if not process.stdout:
                return MonitorResult(
                    success=False,
                    runtime_ms=0,
                    crashed=True,
                )
            
            # Start capture tasks
            serial_task = asyncio.create_task(
                self.capture.capture_serial(process.stdout)
            )
            cpu_task = asyncio.create_task(
                self.capture.capture_cpu_log(self.paths.cpu_log)
            )
            
            # Create a task for process exit
            exit_task = asyncio.create_task(process.wait())
            
            # Main loop
            while True:
                if self._should_stop:
                    # Explicit kill if requested
                    try:
                        process.terminate()
                        await process.wait()
                    except:
                        pass
                    break
                
                # Check if process exited
                if exit_task.done():
                    break
                
                elapsed = time.time() - start
                if timeout and elapsed > timeout:
                    self.log.warning(f"Timeout after {timeout}s")
                    try:
                        process.terminate()
                    except:
                        pass
                    break
                
                await asyncio.sleep(0.1)
            
            # Cleanup
            self.capture.stop()
            
            for task in [serial_task, cpu_task]:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            runtime_ms = int((time.time() - start) * 1000)
            
            # Save logs
            self._save_logs()
            
            return MonitorResult(
                success=not self._crash_info,
                runtime_ms=runtime_ms,
                crashed=self._crash_info is not None,
                crash_info=self._crash_info,
                all_crashes=self._all_crashes,
                total_lines=self.capture.total_lines,
            )
        
        except Exception as e:
            self.log.error(f"Monitor error: {e}")
            await self.runner.stop()
            
            return MonitorResult(
                success=False,
                runtime_ms=int((time.time() - start) * 1000),
                crashed=True,
            )
    
    def _save_logs(self) -> None:
        """Save captured logs to files."""
        try:
            log_dir = self.paths.anvil_log_dir
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Clear old logs
            for f in log_dir.glob("*.log"):
                f.unlink()
            
            serial_file = log_dir / "serial.log"
            cpu_file = log_dir / "cpu.log"
            
            self.log.info(f"💾 Saving logs to {log_dir}")
            
            serial_entries = self.capture.get_serial(lines=10000)
            cpu_entries = self.capture.get_cpu(lines=10000)
            
            serial_file.write_text(
                "\n".join(e.line for e in serial_entries),
                encoding="utf-8",
            )
            cpu_file.write_text(
                "\n".join(e.line for e in cpu_entries),
                encoding="utf-8",
            )
        
        except Exception as e:
            self.log.error(f"Failed to save logs: {e}")
    
    def get_context(self, lines: int = 50) -> list[LogEntry]:
        """Get recent log context."""
        return self.capture.get_context(lines)

