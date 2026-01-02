"""Anvil Build - Binary artifact validation."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from core.logger import Logger, get_logger


class ArtifactType(Enum):
    """Type of build artifact."""
    KERNEL = "kernel"
    BOOTLOADER = "bootloader"
    SERVICE = "service"


@dataclass
class ValidationResult:
    """Result of artifact validation."""
    valid: bool
    artifact_type: ArtifactType
    path: Path
    size: int = 0
    checksum: str = ""
    issues: list[str] = field(default_factory=list)


class ArtifactValidator:
    """
    Validates compiled artifacts for correctness.
    
    Checks:
    - File existence and non-zero size
    - Correct binary format (ELF64, PE64+)
    - Entry point location (kernel in high-half)
    - Integrity checksum
    """
    
    ELF_MAGIC = b"\x7fELF"
    PE_MAGIC = b"MZ"
    
    def __init__(self, log: Optional[Logger] = None):
        self.log = log or get_logger()
    
    def validate_kernel(self, path: Path) -> ValidationResult:
        """
        Validate kernel binary.
        
        Verifies:
        - Is a valid ELF64 file
        - Entry point is in kernel space (>= 0xFFFFFFFF80000000)
        """
        issues = []
        
        if not path.exists():
            return ValidationResult(
                valid=False,
                artifact_type=ArtifactType.KERNEL,
                path=path,
                issues=[f"File not found: {path}"],
            )
        
        size = path.stat().st_size
        if size == 0:
            return ValidationResult(
                valid=False,
                artifact_type=ArtifactType.KERNEL,
                path=path,
                issues=["File is empty"],
            )
        
        # Validate ELF format
        with open(path, "rb") as f:
            magic = f.read(4)
            if magic != self.ELF_MAGIC:
                issues.append(f"Not a valid ELF file (magic: {magic.hex()})")
            else:
                # Check ELF64
                f.seek(4)
                ei_class = f.read(1)
                if ei_class != b"\x02":
                    issues.append("Not ELF64 (expected for x86_64)")
                
                # Check entry point
                f.seek(24)  # e_entry in ELF64
                entry_bytes = f.read(8)
                entry_point = struct.unpack("<Q", entry_bytes)[0]
                
                if entry_point < 0xFFFFFFFF80000000:
                    issues.append(
                        f"Entry point 0x{entry_point:x} not in high-half "
                        "(expected >= 0xFFFFFFFF80000000)"
                    )
        
        checksum = self._compute_checksum(path)
        valid = len(issues) == 0
        
        if valid:
            self.log.success(f"Kernel valid ({size:,} bytes)")
        else:
            self.log.error(f"Kernel invalid: {', '.join(issues)}")
        
        return ValidationResult(
            valid=valid,
            artifact_type=ArtifactType.KERNEL,
            path=path,
            size=size,
            checksum=checksum,
            issues=issues,
        )
    
    def validate_bootloader(self, path: Path) -> ValidationResult:
        """Validate UEFI bootloader (PE64+)."""
        issues = []
        
        if not path.exists():
            return ValidationResult(
                valid=False,
                artifact_type=ArtifactType.BOOTLOADER,
                path=path,
                issues=[f"File not found: {path}"],
            )
        
        size = path.stat().st_size
        if size == 0:
            return ValidationResult(
                valid=False,
                artifact_type=ArtifactType.BOOTLOADER,
                path=path,
                issues=["File is empty"],
            )
        
        # Validate PE format
        with open(path, "rb") as f:
            magic = f.read(2)
            if magic != self.PE_MAGIC:
                issues.append(f"Not a valid PE file (magic: {magic.hex()})")
            else:
                # Get PE signature offset
                f.seek(0x3C)
                pe_offset = struct.unpack("<I", f.read(4))[0]
                
                # Check PE signature
                f.seek(pe_offset)
                pe_sig = f.read(4)
                if pe_sig != b"PE\x00\x00":
                    issues.append("Invalid PE signature")
                else:
                    # Check machine type (x86_64 = 0x8664)
                    machine = struct.unpack("<H", f.read(2))[0]
                    if machine != 0x8664:
                        issues.append(
                            f"Wrong machine type: 0x{machine:x} (expected 0x8664)"
                        )
        
        checksum = self._compute_checksum(path)
        valid = len(issues) == 0
        
        if valid:
            self.log.success(f"Bootloader valid ({size:,} bytes)")
        else:
            self.log.error(f"Bootloader invalid: {', '.join(issues)}")
        
        return ValidationResult(
            valid=valid,
            artifact_type=ArtifactType.BOOTLOADER,
            path=path,
            size=size,
            checksum=checksum,
            issues=issues,
        )
    
    def validate_service(self, path: Path, name: str) -> ValidationResult:
        """Validate a userspace service (ELF64)."""
        issues = []
        
        if not path.exists():
            return ValidationResult(
                valid=False,
                artifact_type=ArtifactType.SERVICE,
                path=path,
                issues=[f"Service '{name}' not found: {path}"],
            )
        
        size = path.stat().st_size
        if size == 0:
            return ValidationResult(
                valid=False,
                artifact_type=ArtifactType.SERVICE,
                path=path,
                issues=[f"Service '{name}' is empty"],
            )
        
        # Check ELF magic
        with open(path, "rb") as f:
            magic = f.read(4)
            if magic != self.ELF_MAGIC:
                issues.append(f"Service '{name}' is not a valid ELF")
        
        checksum = self._compute_checksum(path)
        valid = len(issues) == 0
        
        if valid:
            self.log.success(f"Service '{name}' valid ({size:,} bytes)")
        
        return ValidationResult(
            valid=valid,
            artifact_type=ArtifactType.SERVICE,
            path=path,
            size=size,
            checksum=checksum,
            issues=issues,
        )
    
    def _compute_checksum(self, path: Path) -> str:
        """Compute SHA256 checksum of file."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def generate_manifest(self, results: list[ValidationResult]) -> dict:
        """Generate manifest with all artifact checksums."""
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

