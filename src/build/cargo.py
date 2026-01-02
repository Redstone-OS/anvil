"""Anvil Build - Cargo compilation wrapper."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Any

from core.errors import BuildError
from core.logger import Logger, get_logger


@dataclass
class CargoError:
    """A single Cargo compilation error."""
    level: str  # "error" or "warning"
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    code: Optional[str] = None  # E0001, E0308, etc.
    
    def __str__(self) -> str:
        location = ""
        if self.file:
            location = f"{self.file}"
            if self.line:
                location += f":{self.line}"
                if self.column:
                    location += f":{self.column}"
            location += " - "
        
        code = f"[{self.code}] " if self.code else ""
        return f"{self.level.upper()}: {location}{code}{self.message}"


@dataclass
class BuildResult:
    """Result of a Cargo build."""
    success: bool
    component: str
    profile: str
    duration_ms: int = 0
    errors: list[CargoError] = field(default_factory=list)
    warnings: list[CargoError] = field(default_factory=list)
    output_path: Optional[Path] = None
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


class CargoBuilder:
    """
    Intelligent Cargo build wrapper.
    
    Features:
    - Async builds with real-time output
    - Structured error parsing
    - Multiple target support
    """
    
    # Patterns for parsing Cargo output
    ERROR_PATTERN = re.compile(
        r"^(?P<level>error|warning)(?:\[(?P<code>E\d+)\])?: (?P<message>.+)$"
    )
    LOCATION_PATTERN = re.compile(
        r"^\s*--> (?P<file>[^:]+):(?P<line>\d+):(?P<column>\d+)$"
    )
    
    def __init__(
        self,
        project_root: Path,
        log: Optional[Logger] = None,
        on_output: Optional[Callable[[str], None]] = None,
    ):
        self.project_root = project_root
        self.log = log or get_logger()
        self.on_output = on_output
    
    async def build(
        self,
        component: str,
        path: Path,
        target: Optional[str] = None,
        profile: str = "release",
        features: Optional[list[str]] = None,
    ) -> BuildResult:
        """
        Build a component with Cargo.
        
        Args:
            component: Display name (e.g., "Kernel", "Bootloader")
            path: Path to Cargo.toml directory
            target: Target triple (uses .cargo/config.toml if None)
            profile: Build profile ("release", "debug", or custom)
            features: List of features to enable
        
        Returns:
            BuildResult with success status and any errors
        """
        self.log.info(f"🔨 Building {component} ({profile})...")
        
        # Build command
        cmd = ["cargo", "build"]
        
        if profile == "release":
            cmd.append("--release")
        elif profile != "debug":
            cmd.extend(["--profile", profile])
        
        if target:
            cmd.extend(["--target", target])
        
        if features:
            cmd.extend(["--features", ",".join(features)])
        
        # Execute
        start = time.time()
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            all_stderr: list[str] = []
            
            # Stream output in real-time
            async def read_stream(stream: asyncio.StreamReader, is_stderr: bool) -> None:
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").rstrip()
                    
                    if is_stderr:
                        all_stderr.append(decoded)
                    
                    # Emit to callback or logger
                    if self.on_output:
                        self.on_output(decoded)
                    else:
                        self.log.raw(decoded)
            
            await asyncio.gather(
                read_stream(process.stdout, False),
                read_stream(process.stderr, True),
            )
            
            await process.wait()
            duration_ms = int((time.time() - start) * 1000)
            
            # Parse errors from stderr
            stderr_text = "\n".join(all_stderr)
            errors, warnings = self._parse_output(stderr_text)
            
            success = process.returncode == 0
            
            if success:
                self.log.success(f"{component} built ({duration_ms}ms)")
            else:
                self.log.error(f"{component} failed")
                for err in errors[:5]:
                    self.log.step(str(err))
            
            return BuildResult(
                success=success,
                component=component,
                profile=profile,
                duration_ms=duration_ms,
                errors=errors,
                warnings=warnings,
            )
        
        except FileNotFoundError:
            raise BuildError("Cargo not found. Is Rust installed?", component)
        except Exception as e:
            raise BuildError(f"Cargo execution failed: {e}", component)
    
    def _parse_output(self, output: str) -> tuple[list[CargoError], list[CargoError]]:
        """Parse Cargo stderr into structured errors."""
        errors: list[CargoError] = []
        warnings: list[CargoError] = []
        
        current: Optional[CargoError] = None
        
        for line in output.split("\n"):
            # Match error/warning header
            match = self.ERROR_PATTERN.match(line)
            if match:
                if current:
                    (errors if current.level == "error" else warnings).append(current)
                
                current = CargoError(
                    level=match.group("level"),
                    message=match.group("message"),
                    code=match.group("code"),
                )
                continue
            
            # Match location info
            if current:
                loc_match = self.LOCATION_PATTERN.match(line)
                if loc_match:
                    current.file = loc_match.group("file")
                    current.line = int(loc_match.group("line"))
                    current.column = int(loc_match.group("column"))
        
        # Don't forget the last one
        if current:
            (errors if current.level == "error" else warnings).append(current)
        
        return errors, warnings
    
    async def check_target(self, target: str) -> bool:
        """Check if a Rust target is installed."""
        try:
            process = await asyncio.create_subprocess_exec(
                "rustup", "target", "list", "--installed",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            installed = stdout.decode().strip().split("\n")
            return target in installed
        except FileNotFoundError:
            return False
    
    async def install_target(self, target: str) -> bool:
        """Install a Rust target via rustup."""
        self.log.info(f"📥 Installing target: {target}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                "rustup", "target", "add", target,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            
            if process.returncode == 0:
                self.log.success(f"Target {target} installed")
                return True
            else:
                self.log.error(f"Failed to install {target}")
                return False
        except FileNotFoundError:
            self.log.error("rustup not found")
            return False

