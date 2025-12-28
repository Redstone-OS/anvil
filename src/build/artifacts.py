"""
Anvil Build - Validação de artefatos gerados
"""

import hashlib
import struct
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from core.logger import log
from core.exceptions import ValidationError


class ArtifactType(Enum):
    """Tipo de artefato."""
    KERNEL = "kernel"
    BOOTLOADER = "bootloader"
    SERVICE = "service"


@dataclass
class ValidationResult:
    """Resultado da validação de um artefato."""
    valid: bool
    artifact_type: ArtifactType
    path: Path
    size: int = 0
    checksum: str = ""
    issues: list[str] = None
    
    def __post_init__(self):
        if self.issues is None:
            self.issues = []


class ArtifactValidator:
    """Validador de artefatos de build."""
    
    # ELF Magic
    ELF_MAGIC = b"\x7fELF"
    
    # PE Magic (MZ header)
    PE_MAGIC = b"MZ"
    
    def validate_kernel(self, path: Path) -> ValidationResult:
        """
        Valida binário do kernel.
        
        Verifica:
        - Arquivo existe e tem tamanho > 0
        - É ELF64 válido
        - Entry point está no high-half (kernel space)
        """
        issues = []
        
        if not path.exists():
            return ValidationResult(
                valid=False,
                artifact_type=ArtifactType.KERNEL,
                path=path,
                issues=[f"Arquivo não encontrado: {path}"],
            )
        
        size = path.stat().st_size
        if size == 0:
            return ValidationResult(
                valid=False,
                artifact_type=ArtifactType.KERNEL,
                path=path,
                size=0,
                issues=["Arquivo vazio"],
            )
        
        # Verificar ELF
        with open(path, "rb") as f:
            magic = f.read(4)
            if magic != self.ELF_MAGIC:
                issues.append(f"Não é um arquivo ELF válido (magic: {magic.hex()})")
            else:
                # ELF64 check
                f.seek(4)
                ei_class = f.read(1)
                if ei_class != b"\x02":
                    issues.append("Não é ELF64 (esperado para x86_64)")
                
                # Entry point check
                f.seek(24)  # e_entry offset in ELF64
                entry_bytes = f.read(8)
                entry_point = struct.unpack("<Q", entry_bytes)[0]
                
                # Entry point deve estar em 0xFFFFFFFF80000000+ (high-half)
                if entry_point < 0xFFFFFFFF80000000:
                    issues.append(
                        f"Entry point {hex(entry_point)} não está no high-half "
                        "(esperado >= 0xFFFFFFFF80000000)"
                    )
        
        checksum = self._compute_checksum(path)
        
        valid = len(issues) == 0
        if valid:
            log.success(f"Kernel válido ({size:,} bytes)")
        else:
            log.error(f"Kernel inválido: {', '.join(issues)}")
        
        return ValidationResult(
            valid=valid,
            artifact_type=ArtifactType.KERNEL,
            path=path,
            size=size,
            checksum=checksum,
            issues=issues,
        )
    
    def validate_bootloader(self, path: Path) -> ValidationResult:
        """
        Valida binário do bootloader (UEFI PE64+).
        """
        issues = []
        
        if not path.exists():
            return ValidationResult(
                valid=False,
                artifact_type=ArtifactType.BOOTLOADER,
                path=path,
                issues=[f"Arquivo não encontrado: {path}"],
            )
        
        size = path.stat().st_size
        if size == 0:
            return ValidationResult(
                valid=False,
                artifact_type=ArtifactType.BOOTLOADER,
                path=path,
                size=0,
                issues=["Arquivo vazio"],
            )
        
        # Verificar PE
        with open(path, "rb") as f:
            magic = f.read(2)
            if magic != self.PE_MAGIC:
                issues.append(f"Não é um arquivo PE válido (magic: {magic.hex()})")
            else:
                # Verificar PE signature offset
                f.seek(0x3C)
                pe_offset = struct.unpack("<I", f.read(4))[0]
                
                f.seek(pe_offset)
                pe_sig = f.read(4)
                if pe_sig != b"PE\x00\x00":
                    issues.append("Assinatura PE inválida")
                else:
                    # Verificar machine type (x86_64)
                    machine = struct.unpack("<H", f.read(2))[0]
                    if machine != 0x8664:
                        issues.append(f"Machine type incorreto: {hex(machine)} (esperado 0x8664)")
        
        checksum = self._compute_checksum(path)
        
        valid = len(issues) == 0
        if valid:
            log.success(f"Bootloader válido ({size:,} bytes)")
        else:
            log.error(f"Bootloader inválido: {', '.join(issues)}")
        
        return ValidationResult(
            valid=valid,
            artifact_type=ArtifactType.BOOTLOADER,
            path=path,
            size=size,
            checksum=checksum,
            issues=issues,
        )
    
    def validate_service(self, path: Path, name: str) -> ValidationResult:
        """Valida binário de serviço (ELF64)."""
        issues = []
        
        if not path.exists():
            return ValidationResult(
                valid=False,
                artifact_type=ArtifactType.SERVICE,
                path=path,
                issues=[f"Serviço {name} não encontrado: {path}"],
            )
        
        size = path.stat().st_size
        if size == 0:
            return ValidationResult(
                valid=False,
                artifact_type=ArtifactType.SERVICE,
                path=path,
                size=0,
                issues=[f"Serviço {name} vazio"],
            )
        
        # Verificar ELF
        with open(path, "rb") as f:
            magic = f.read(4)
            if magic != self.ELF_MAGIC:
                issues.append(f"Serviço {name} não é ELF válido")
        
        checksum = self._compute_checksum(path)
        
        valid = len(issues) == 0
        if valid:
            log.success(f"Serviço {name} válido ({size:,} bytes)")
        
        return ValidationResult(
            valid=valid,
            artifact_type=ArtifactType.SERVICE,
            path=path,
            size=size,
            checksum=checksum,
            issues=issues,
        )
    
    def _compute_checksum(self, path: Path) -> str:
        """Computa SHA256 do arquivo."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def generate_manifest(self, results: list[ValidationResult]) -> dict:
        """Gera manifesto com checksums de todos os artefatos."""
        return {
            "artifacts": [
                {
                    "type": r.artifact_type.value,
                    "path": str(r.path.name),
                    "size": r.size,
                    "sha256": r.checksum,
                    "valid": r.valid,
                }
                for r in results
            ]
        }
