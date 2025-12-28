"""
Anvil CLI - Interface de linha de comando
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from anvil import __version__
from core.config import load_config, AnvilConfig
from core.paths import PathResolver
from core.logger import log, console, setup_logging
from build.cargo import CargoBuilder
from build.artifacts import ArtifactValidator
from build.initramfs import InitramfsBuilder
from build.dist import DistBuilder
from runner.monitor import QemuMonitor
from runner.qemu import QemuConfig
from analysis.diagnostics import DiagnosticEngine
from analysis.log_parser import LogParser
from analysis.binary_inspector import BinaryInspector


# CLI App
app = typer.Typer(
    name="anvil",
    help="🔨 Anvil - Build, Run and Diagnostic Tool for RedstoneOS",
    add_completion=False,
)


def get_context() -> tuple[PathResolver, AnvilConfig]:
    """Obtém contexto de paths e config."""
    config = load_config()
    paths = PathResolver(config.project_root)
    return paths, config


# ============================================================================
# Build Commands
# ============================================================================

@app.command()
def build(
    profile: str = typer.Option("release", "--profile", "-p", help="Build profile"),
    kernel_only: bool = typer.Option(False, "--kernel", "-k", help="Build only kernel"),
    bootloader_only: bool = typer.Option(False, "--bootloader", "-b", help="Build only bootloader"),
    services_only: bool = typer.Option(False, "--services", "-s", help="Build only services"),
    no_dist: bool = typer.Option(False, "--no-dist", help="Skip dist preparation"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Build RedstoneOS components."""
    setup_logging(verbose=verbose)
    asyncio.run(_build_async(profile, kernel_only, bootloader_only, services_only, no_dist))


async def _build_async(
    profile: str,
    kernel_only: bool,
    bootloader_only: bool,
    services_only: bool,
    no_dist: bool,
):
    paths, config = get_context()
    builder = CargoBuilder(paths.project_root)
    validator = ArtifactValidator()
    
    log.header(f"Build RedstoneOS ({profile})")
    
    results = []
    
    # Decidir o que compilar
    build_kernel = not (bootloader_only or services_only)
    build_bootloader = not (kernel_only or services_only)
    build_services = not (kernel_only or bootloader_only)
    
    # Kernel
    if build_kernel:
        result = await builder.build(
            "Kernel",
            paths.forge,
            target=None,  # Uses .cargo/config.toml
            profile=profile,
        )
        results.append(result)
        
        if result.success:
            validator.validate_kernel(paths.kernel_binary(profile))
    
    # Bootloader
    if build_bootloader:
        result = await builder.build(
            "Bootloader",
            paths.ignite,
            target="x86_64-unknown-uefi",
            profile=profile,
        )
        results.append(result)
        
        if result.success:
            validator.validate_bootloader(paths.bootloader_binary(profile))
    
    # Services
    if build_services:
        for svc in config.components.services:
            svc_path = paths.services / svc.name
            result = await builder.build(
                svc.name,
                svc_path,
                target=svc.target,
                profile=profile,
            )
            results.append(result)
    
    # Verificar resultados
    all_success = all(r.success for r in results)
    
    if not all_success:
        log.error("Build falhou!")
        raise typer.Exit(1)
    
    # Preparar dist
    if not no_dist and all_success:
        dist_builder = DistBuilder(paths, config)
        dist_builder.prepare(profile)
        
        initramfs_builder = InitramfsBuilder(paths, config)
        await initramfs_builder.build(profile)
    
    log.success("Build concluído!")


# ============================================================================
# Run Commands
# ============================================================================

@app.command()
def run(
    profile: str = typer.Option("release", "--profile", "-p", help="Build profile"),
    no_build: bool = typer.Option(False, "--no-build", help="Skip build step"),
    timeout: Optional[float] = typer.Option(None, "--timeout", "-t", help="Timeout in seconds"),
    gdb: bool = typer.Option(False, "--gdb", "-g", help="Enable GDB server"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Build and run RedstoneOS in QEMU with monitoring."""
    setup_logging(verbose=verbose)
    asyncio.run(_run_async(profile, no_build, timeout, gdb))


async def _run_async(profile: str, no_build: bool, timeout: Optional[float], gdb: bool):
    paths, config = get_context()
    
    # Build se necessário
    if not no_build:
        await _build_async(profile, False, False, False, False)
    
    log.header("Executando QEMU")
    
    # Configurar monitor
    qemu_config = QemuConfig(
        memory=config.qemu.memory,
        debug_flags=config.qemu.logging.flags,
        enable_gdb=gdb,
    )
    
    monitor = QemuMonitor(
        paths, 
        config,
        stop_on_exception=config.analysis.stop_on_exception,
    )
    
    # Executar com monitoramento
    result = await monitor.run_monitored(qemu_config, timeout)
    
    # Se houve crash, analisar
    if result.crashed and result.crash_info:
        log.warning("Crash detectado! Analisando...")
        
        engine = DiagnosticEngine(paths, config)
        diagnosis = await engine.analyze_crash(
            result.crash_info.exception_type,
            result.crash_info.context_lines,
        )
        engine.print_diagnosis(diagnosis)
    
    # Resumo
    console.print()
    console.print(f"[dim]Runtime: {result.runtime_ms}ms | Linhas: {result.total_lines}[/dim]")


# ============================================================================
# Analysis Commands  
# ============================================================================

@app.command()
def analyze(
    log_file: Path = typer.Argument(..., help="Log file to analyze"),
    context: int = typer.Option(50, "--context", "-c", help="Context lines"),
):
    """Analyze a QEMU log file for errors."""
    setup_logging()
    
    if not log_file.exists():
        log.error(f"Arquivo não encontrado: {log_file}")
        raise typer.Exit(1)
    
    log.header(f"Analisando {log_file.name}")
    
    parser = LogParser(context_size=context)
    
    for event in parser.parse_file(log_file):
        if event.event_type == "exception":
            console.print(f"[red]💥 {event.raw_line}[/red]")
    
    # Resumo
    summary = parser.analyze_summary()
    
    console.print()
    table = Table(title="Resumo da Análise")
    table.add_column("Métrica")
    table.add_column("Valor")
    
    table.add_row("Total de linhas", str(summary["total_lines"]))
    table.add_row("Exceções", str(summary["exceptions_count"]))
    
    for event_type, count in summary["events_by_type"].items():
        table.add_row(f"Eventos: {event_type}", str(count))
    
    console.print(table)


@app.command()
def inspect(
    check_sse: bool = typer.Option(False, "--check-sse", help="Check for SSE instructions"),
    symbols: bool = typer.Option(False, "--symbols", help="List symbols"),
    sections: bool = typer.Option(False, "--sections", help="List sections"),
    address: Optional[str] = typer.Option(None, "--address", "-a", help="Disassemble at address"),
):
    """Inspect kernel binary."""
    setup_logging()
    asyncio.run(_inspect_async(check_sse, symbols, sections, address))


async def _inspect_async(check_sse: bool, symbols: bool, sections: bool, address: Optional[str]):
    paths, config = get_context()
    inspector = BinaryInspector(paths)
    
    kernel = paths.kernel_binary()
    
    if not kernel.exists():
        log.error(f"Kernel não encontrado: {kernel}")
        raise typer.Exit(1)
    
    log.header(f"Inspecionando {kernel.name}")
    
    if check_sse:
        violations = await inspector.check_sse_instructions(kernel)
        if violations:
            console.print(f"\n[red]Encontradas {len(violations)} instruções SSE/AVX:[/red]")
            for v in violations[:20]:
                console.print(f"  0x{v.address:x}: {v.instruction}")
                if v.symbol:
                    console.print(f"    em {v.symbol}")
    
    if sections:
        secs = await inspector.analyze_sections(kernel)
        table = Table(title="Seções")
        table.add_column("Nome")
        table.add_column("Endereço", justify="right")
        table.add_column("Tamanho", justify="right")
        
        for sec in secs:
            table.add_row(
                sec.name,
                f"0x{sec.address:x}",
                f"{sec.size:,}",
            )
        
        console.print(table)
    
    if address:
        addr = int(address.replace("0x", ""), 16)
        disasm = await inspector.disassemble_at(kernel, addr)
        
        if disasm:
            console.print(f"\nDisassembly @ 0x{addr:x}:")
            for a, _, asm in disasm.instructions:
                marker = "→" if a == addr else " "
                console.print(f"  {marker} 0x{a:x}: {asm}")


# ============================================================================
# Utility Commands
# ============================================================================

@app.command()
def stats(
    path: Path = typer.Option(None, "--path", "-p", help="Path to analyze"),
):
    """Count lines of code in the project."""
    import os
    
    paths, config = get_context()
    base_path = path or paths.forge / "src"
    
    log.header(f"Estatísticas: {base_path}")
    
    total_lines = 0
    files_count = 0
    
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".rs"):
                files_count += 1
                file_path = Path(root) / file
                
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped and not stripped.startswith("//"):
                            total_lines += 1
    
    table = Table()
    table.add_column("Métrica")
    table.add_column("Valor", justify="right")
    
    table.add_row("Arquivos .rs", str(files_count))
    table.add_row("Linhas de código", f"{total_lines:,}")
    
    console.print(table)


@app.command()
def clean():
    """Clean build artifacts."""
    import shutil
    
    paths, _ = get_context()
    
    log.header("Limpando Artefatos")
    
    targets = [
        paths.forge / "target",
        paths.ignite / "target",
        paths.dist,
    ]
    
    # Add service targets
    for svc_dir in paths.services.iterdir():
        if svc_dir.is_dir():
            targets.append(svc_dir / "target")
    
    for target in targets:
        if target.exists():
            log.step(f"Removendo {paths.relative(target)}")
            shutil.rmtree(target)
    
    log.success("Limpeza concluída!")


@app.command()
def env():
    """Show environment information."""
    import subprocess
    
    paths, config = get_context()
    
    log.header("Ambiente")
    
    # Diretórios
    console.print("\n[cyan]📂 Diretórios:[/cyan]")
    console.print(f"   Projeto: {paths.project_root}")
    console.print(f"   Forge:   {paths.forge}")
    console.print(f"   Ignite:  {paths.ignite}")
    
    # Rust
    console.print("\n[cyan]🦀 Rust:[/cyan]")
    try:
        rustc = subprocess.run(["rustc", "--version"], capture_output=True, text=True)
        console.print(f"   {rustc.stdout.strip()}")
        cargo = subprocess.run(["cargo", "--version"], capture_output=True, text=True)
        console.print(f"   {cargo.stdout.strip()}")
    except FileNotFoundError:
        console.print("   [red]Rust não encontrado[/red]")
    
    # Services
    console.print("\n[cyan]📦 Serviços:[/cyan]")
    for svc in config.components.services:
        console.print(f"   - {svc.name} ({svc.path})")


@app.command()
def menu():
    """Launch interactive TUI menu."""
    from tui import run_tui
    run_tui()


@app.command()
def version():
    """Show Anvil version."""
    console.print(f"🔨 Anvil v{__version__}")


if __name__ == "__main__":
    app()
