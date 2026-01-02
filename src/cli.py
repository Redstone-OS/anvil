"""Anvil CLI - Modern command-line interface."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

__version__ = "5.0.0"
from core import Context, load_config, get_logger
from build import CargoBuilder, ArtifactValidator, DistBuilder, InitramfsBuilder, ImageBuilder
from runner import QemuMonitor, QemuConfig, PipeListener
from analysis import DiagnosticEngine, BinaryInspector, LogParser


# ============================================================================
# App Definition
# ============================================================================

app = typer.Typer(
    name="anvil",
    help="🔨 Anvil 0.0.5 - Build, Run and Diagnostic Tool for RedstoneOS",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


def get_context(verbose: bool = False) -> Context:
    """Create execution context."""
    return Context.create(verbose=verbose)


# ============================================================================
# Build Commands
# ============================================================================

@app.command()
def build(
    profile: str = typer.Option("release", "-p", "--profile", help="Build profile"),
    kernel_only: bool = typer.Option(False, "-k", "--kernel", help="Build only kernel"),
    bootloader_only: bool = typer.Option(False, "-b", "--bootloader", help="Build only bootloader"),
    services_only: bool = typer.Option(False, "-s", "--services", help="Build only services"),
    no_dist: bool = typer.Option(False, "--no-dist", help="Skip dist preparation"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
):
    """Build RedstoneOS components."""
    asyncio.run(_build(profile, kernel_only, bootloader_only, services_only, no_dist, verbose))


async def _build(
    profile: str,
    kernel_only: bool,
    bootloader_only: bool,
    services_only: bool,
    no_dist: bool,
    verbose: bool,
):
    ctx = get_context(verbose)
    builder = CargoBuilder(ctx.paths.root, ctx.log)
    validator = ArtifactValidator(ctx.log)
    
    ctx.log.header(f"Build RedstoneOS ({profile})")
    
    results = []
    
    # Determine what to build
    build_kernel = not (bootloader_only or services_only)
    build_bootloader = not (kernel_only or services_only)
    build_services = not (kernel_only or bootloader_only)
    
    # Kernel
    if build_kernel:
        result = await builder.build("Kernel", ctx.paths.forge, profile=profile)
        results.append(result)
        
        if result.success:
            validator.validate_kernel(ctx.paths.kernel_binary(profile))
    
    # Bootloader
    if build_bootloader:
        result = await builder.build(
            "Bootloader",
            ctx.paths.ignite,
            target="x86_64-unknown-uefi",
            profile=profile,
        )
        results.append(result)
        
        if result.success:
            validator.validate_bootloader(ctx.paths.bootloader_binary(profile))
    
    # Services
    if build_services:
        for svc in ctx.config.components.services:
            svc_path = ctx.paths.root / svc.path
            result = await builder.build(
                svc.name,
                svc_path,
                target=svc.target,
                profile=profile,
            )
            results.append(result)
    
    # Check results
    all_success = all(r.success for r in results)
    
    if not all_success:
        ctx.log.error("Build failed!")
        raise typer.Exit(1)
    
    # Prepare dist
    if not no_dist and all_success:
        DistBuilder(ctx.paths, ctx.config, ctx.log).prepare(profile)
        await InitramfsBuilder(ctx.paths, ctx.config, ctx.log).build(profile)
    
    ctx.log.success("Build complete!")


# ============================================================================
# Run Commands
# ============================================================================

@app.command()
def run(
    profile: str = typer.Option("release", "-p", "--profile", help="Build profile"),
    no_build: bool = typer.Option(False, "--no-build", help="Skip build"),
    timeout: Optional[float] = typer.Option(None, "-t", "--timeout", help="Timeout in seconds"),
    gdb: bool = typer.Option(False, "-g", "--gdb", help="Enable GDB server"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
):
    """Build and run RedstoneOS in QEMU with monitoring."""
    asyncio.run(_run(profile, no_build, timeout, gdb, verbose))


async def _run(
    profile: str,
    no_build: bool,
    timeout: Optional[float],
    gdb: bool,
    verbose: bool,
):
    ctx = get_context(verbose)
    
    # Build if needed
    if not no_build:
        await _build(profile, False, False, False, False, verbose)
    
    ctx.log.header("Running QEMU")
    
    qemu_config = QemuConfig(
        memory=ctx.config.qemu.memory,
        debug_flags=ctx.config.qemu.logging.flags,
        enable_gdb=gdb,
    )
    
    if gdb:
        ctx.log.info("Connect debugger to localhost:1234")
    
    monitor = QemuMonitor(
        ctx.paths,
        ctx.config,
        ctx.log,
        stop_on_exception=ctx.config.analysis.stop_on_exception,
    )
    
    result = await monitor.run_monitored(qemu_config, timeout)
    
    # Analyze crash if detected
    if result.crashed and result.crash_info:
        ctx.log.warning("Crash detected! Analyzing...")
        
        engine = DiagnosticEngine(ctx.paths, ctx.config, ctx.log)
        diagnosis = await engine.analyze(result.crash_info, profile)
        engine.print_diagnosis(diagnosis)
    
    # Summary
    console.print()
    console.print(f"[dim]Runtime: {result.runtime_ms}ms | Lines: {result.total_lines}[/]")


# ============================================================================
# Image Commands
# ============================================================================

@app.command()
def vdi(
    profile: str = typer.Option("release", "-p", "--profile", help="Build profile"),
    no_build: bool = typer.Option(False, "--no-build", help="Skip build"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
):
    """Create a VDI disk image of RedstoneOS."""
    asyncio.run(_vdi(profile, no_build, verbose))


async def _vdi(profile: str, no_build: bool, verbose: bool):
    ctx = get_context(verbose)
    
    if not no_build:
        await _build(profile, False, False, False, False, verbose)
    
    await ImageBuilder(ctx.paths, ctx.config, ctx.log).build_vdi(profile)


@app.command()
def listen(
    pipe: str = typer.Argument(r"\\.\pipe\VBoxCom1", help="Named pipe path"),
):
    """Listen for serial logs via Named Pipe (VirtualBox)."""
    ctx = get_context()
    
    listener = PipeListener(pipe, ctx.log)
    try:
        asyncio.run(listener.start())
    except KeyboardInterrupt:
        ctx.log.info("Stopping listener...")
        listener.stop()


# ============================================================================
# Analysis Commands
# ============================================================================

@app.command()
def analyze(
    log_file: Path = typer.Argument(..., help="Log file to analyze"),
    context: int = typer.Option(50, "-c", "--context", help="Context lines"),
):
    """Analyze a QEMU log file for errors."""
    ctx = get_context()
    
    if not log_file.exists():
        ctx.log.error(f"File not found: {log_file}")
        raise typer.Exit(1)
    
    ctx.log.header(f"Analyzing {log_file.name}")
    
    parser = LogParser(context_size=context)
    
    for event in parser.parse_file(log_file):
        if event.event_type == "exception":
            console.print(f"[red]💥 {event.raw_line}[/]")
    
    summary = parser.summary()
    
    console.print()
    table = Table(title="Analysis Summary")
    table.add_column("Metric")
    table.add_column("Value")
    
    table.add_row("Total lines", str(summary["total_lines"]))
    table.add_row("Exceptions", str(summary["exceptions_count"]))
    
    for event_type, count in summary["events_by_type"].items():
        table.add_row(f"Events: {event_type}", str(count))
    
    console.print(table)


@app.command()
def inspect(
    check_sse: bool = typer.Option(False, "--check-sse", help="Check for SSE instructions"),
    symbols: bool = typer.Option(False, "--symbols", help="List symbols"),
    sections: bool = typer.Option(False, "--sections", help="List sections"),
    address: Optional[str] = typer.Option(None, "-a", "--address", help="Disassemble at address"),
):
    """Inspect kernel binary."""
    asyncio.run(_inspect(check_sse, symbols, sections, address))


async def _inspect(
    check_sse: bool,
    symbols: bool,
    sections: bool,
    address: Optional[str],
):
    ctx = get_context()
    inspector = BinaryInspector(ctx.paths, ctx.log)
    
    kernel = ctx.paths.kernel_binary()
    
    if not kernel.exists():
        ctx.log.error(f"Kernel not found: {kernel}")
        raise typer.Exit(1)
    
    ctx.log.header(f"Inspecting {kernel.name}")
    
    if check_sse:
        violations = await inspector.check_sse(kernel)
        if violations:
            console.print(f"\n[red]Found {len(violations)} SSE/AVX instructions:[/]")
            for v in violations[:20]:
                console.print(f"  0x{v.address:x}: {v.instruction}")
                if v.symbol:
                    console.print(f"    in {v.symbol}")
    
    if sections:
        secs = await inspector.get_sections(kernel)
        table = Table(title="Sections")
        table.add_column("Name")
        table.add_column("Address", justify="right")
        table.add_column("Size", justify="right")
        
        for sec in secs:
            table.add_row(sec.name, f"0x{sec.address:x}", f"{sec.size:,}")
        
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
    path: Optional[Path] = typer.Option(None, "-p", "--path", help="Path to analyze"),
):
    """Count lines of code in the project."""
    import os
    
    ctx = get_context()
    base_path = path or ctx.paths.forge / "src"
    
    ctx.log.header(f"Statistics: {base_path}")
    
    total_lines = 0
    files_count = 0
    
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".rs"):
                files_count += 1
                file_path = Path(root) / file
                
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    in_block = False
                    for line in f:
                        s = line.strip()
                        if not s:
                            continue
                        
                        # Handle block comments
                        if in_block:
                            if "*/" in s:
                                in_block = False
                                s = s.split("*/", 1)[1].strip()
                                if not s:
                                    continue
                            else:
                                continue
                        
                        if s.startswith("/*"):
                            if "*/" in s:
                                s = s.split("*/", 1)[1].strip()
                                if not s:
                                    continue
                            else:
                                in_block = True
                                continue
                        
                        # Skip single-line comments
                        if s.startswith("//") or not s:
                            continue
                            
                        total_lines += 1
    
    table = Table()
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    
    table.add_row(".rs files", str(files_count))
    table.add_row("Lines of code", f"{total_lines:,}")
    
    console.print(table)


@app.command()
def clean():
    """Clean build artifacts."""
    import shutil
    
    ctx = get_context()
    ctx.log.header("Cleaning Artifacts")
    
    targets = [
        ctx.paths.forge / "target",
        ctx.paths.ignite / "target",
        ctx.paths.dist,
    ]
    
    for svc_dir in ctx.paths.services.iterdir():
        if svc_dir.is_dir():
            targets.append(svc_dir / "target")
    
    for target in targets:
        if target.exists():
            ctx.log.step(f"Removing {ctx.paths.relative(target)}")
            shutil.rmtree(target)
    
    ctx.log.success("Clean complete!")


@app.command()
def env():
    """Show environment information."""
    import subprocess
    
    ctx = get_context()
    ctx.log.header("Environment")
    
    console.print("\n[cyan]📂 Directories:[/]")
    console.print(f"   Project: {ctx.paths.root}")
    console.print(f"   Forge:   {ctx.paths.forge}")
    console.print(f"   Ignite:  {ctx.paths.ignite}")
    
    console.print("\n[cyan]🦀 Rust:[/]")
    try:
        rustc = subprocess.run(["rustc", "--version"], capture_output=True, text=True)
        console.print(f"   {rustc.stdout.strip()}")
        cargo = subprocess.run(["cargo", "--version"], capture_output=True, text=True)
        console.print(f"   {cargo.stdout.strip()}")
    except FileNotFoundError:
        console.print("   [red]Rust not found[/]")
    
    console.print("\n[cyan]📦 Services:[/]")
    for svc in ctx.config.components.services:
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


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()

