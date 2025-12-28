"""
Anvil Build - Wrapper inteligente para Cargo
"""

import asyncio
import subprocess
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.logger import log, console
from core.exceptions import BuildError


@dataclass
class CargoError:
    """Erro de compilação do Cargo."""
    level: str  # error, warning
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    code: Optional[str] = None  # E0001, etc.
    
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
    """Resultado de uma compilação."""
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
    """Wrapper inteligente para Cargo com parsing de erros."""
    
    # Regex para parsing de erros do Cargo
    ERROR_PATTERN = re.compile(
        r"^(?P<level>error|warning)(?:\[(?P<code>E\d+)\])?: (?P<message>.+)$"
    )
    LOCATION_PATTERN = re.compile(
        r"^\s*--> (?P<file>[^:]+):(?P<line>\d+):(?P<column>\d+)$"
    )
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
    
    async def build(
        self,
        component: str,
        path: Path,
        target: Optional[str] = None,
        profile: str = "release",
        features: Optional[list[str]] = None,
    ) -> BuildResult:
        """
        Compila componente e retorna resultado estruturado.
        """
        log.info(f"🔨 Compilando {component} ({profile})...")
        
        # Construir comando
        cmd = ["cargo", "build"]
        
        if profile == "release":
            cmd.append("--release")
        elif profile != "debug":
            cmd.extend(["--profile", profile])
        
        if target:
            cmd.extend(["--target", target])
        
        if features:
            cmd.extend(["--features", ",".join(features)])
        
        # Executar
        import time
        start_time = time.time()
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Parsear erros
            errors, warnings = self._parse_output(stderr.decode("utf-8", errors="replace"))
            
            success = process.returncode == 0
            
            if success:
                log.success(f"{component} compilado ({duration_ms}ms)")
            else:
                log.error(f"{component} falhou")
                for err in errors[:5]:  # Mostrar primeiros 5 erros
                    console.print(f"  [red]→ {err}[/red]")
            
            return BuildResult(
                success=success,
                component=component,
                profile=profile,
                duration_ms=duration_ms,
                errors=errors,
                warnings=warnings,
            )
            
        except FileNotFoundError:
            raise BuildError("Cargo não encontrado. Rust está instalado?", component)
        except Exception as e:
            raise BuildError(f"Erro ao executar Cargo: {e}", component)
    
    def _parse_output(self, output: str) -> tuple[list[CargoError], list[CargoError]]:
        """Parseia output do Cargo para extrair erros e warnings."""
        errors: list[CargoError] = []
        warnings: list[CargoError] = []
        
        current_error: Optional[CargoError] = None
        
        for line in output.split("\n"):
            # Tentar match de erro/warning
            match = self.ERROR_PATTERN.match(line)
            if match:
                if current_error:
                    if current_error.level == "error":
                        errors.append(current_error)
                    else:
                        warnings.append(current_error)
                
                current_error = CargoError(
                    level=match.group("level"),
                    message=match.group("message"),
                    code=match.group("code"),
                )
                continue
            
            # Tentar match de localização
            if current_error:
                loc_match = self.LOCATION_PATTERN.match(line)
                if loc_match:
                    current_error.file = loc_match.group("file")
                    current_error.line = int(loc_match.group("line"))
                    current_error.column = int(loc_match.group("column"))
        
        # Último erro
        if current_error:
            if current_error.level == "error":
                errors.append(current_error)
            else:
                warnings.append(current_error)
        
        return errors, warnings
    
    async def check_targets(self, targets: list[str]) -> dict[str, bool]:
        """Verifica se targets estão instalados."""
        result = {}
        
        try:
            process = await asyncio.create_subprocess_exec(
                "rustup", "target", "list", "--installed",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            installed = stdout.decode().strip().split("\n")
            
            for target in targets:
                result[target] = target in installed
            
        except FileNotFoundError:
            for target in targets:
                result[target] = False
        
        return result
    
    async def install_target(self, target: str) -> bool:
        """Instala target via rustup."""
        log.info(f"📥 Instalando target {target}...")
        
        try:
            process = await asyncio.create_subprocess_exec(
                "rustup", "target", "add", target,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            
            if process.returncode == 0:
                log.success(f"Target {target} instalado")
                return True
            else:
                log.error(f"Falha ao instalar {target}")
                return False
                
        except FileNotFoundError:
            log.error("rustup não encontrado")
            return False
