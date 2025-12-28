"""
Anvil TUI - Interface interativa com Rich
"""

import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from core.config import load_config
from core.paths import PathResolver
from core.logger import log, console


def show_menu() -> None:
    """Exibe menu principal."""
    console.clear()
    
    console.print(Panel(
        "[bold cyan]🔨 Anvil - RedstoneOS[/bold cyan]\n"
        "[dim]Build System v4.0[/dim]",
        border_style="cyan",
    ))
    
    console.print()
    console.print("[yellow]┌─ Build ─────────────────────────────┐[/yellow]")
    console.print("[yellow]│[/yellow] [green][1][/green] Build Release                   [yellow]│[/yellow]")
    console.print("[yellow]│[/yellow] [dim][2][/dim] Build Kernel Only               [yellow]│[/yellow]")
    console.print("[yellow]│[/yellow] [dim][3][/dim] Build Bootloader Only           [yellow]│[/yellow]")
    console.print("[yellow]│[/yellow] [dim][4][/dim] Build Services Only             [yellow]│[/yellow]")
    console.print("[yellow]└─────────────────────────────────────┘[/yellow]")
    
    console.print()
    console.print("[yellow]┌─ Run ───────────────────────────────┐[/yellow]")
    console.print("[yellow]│[/yellow] [green][5][/green] Run QEMU (com monitoramento)    [yellow]│[/yellow]")
    console.print("[yellow]│[/yellow] [dim][6][/dim] Run QEMU + GDB                  [yellow]│[/yellow]")
    console.print("[yellow]└─────────────────────────────────────┘[/yellow]")
    
    console.print()
    console.print("[yellow]┌─ Analysis ──────────────────────────┐[/yellow]")
    console.print("[yellow]│[/yellow] [dim][7][/dim] Analyze Last Log                [yellow]│[/yellow]")
    console.print("[yellow]│[/yellow] [dim][8][/dim] Inspect Kernel (SSE check)      [yellow]│[/yellow]")
    console.print("[yellow]│[/yellow] [dim][9][/dim] Code Statistics                 [yellow]│[/yellow]")
    console.print("[yellow]└─────────────────────────────────────┘[/yellow]")
    
    console.print()
    console.print("[yellow]┌─ Utilities ─────────────────────────┐[/yellow]")
    console.print("[yellow]│[/yellow] [dim][C][/dim] Clean                           [yellow]│[/yellow]")
    console.print("[yellow]│[/yellow] [dim][E][/dim] Environment                     [yellow]│[/yellow]")
    console.print("[yellow]│[/yellow] [red][Q][/red] Quit                            [yellow]│[/yellow]")
    console.print("[yellow]└─────────────────────────────────────┘[/yellow]")
    console.print()


async def handle_choice(choice: str) -> bool:
    """
    Processa escolha do menu.
    
    Returns:
        True para continuar, False para sair
    """
    from build.cargo import CargoBuilder
    from build.dist import DistBuilder
    from build.initramfs import InitramfsBuilder
    from build.artifacts import ArtifactValidator
    from runner.monitor import QemuMonitor
    from runner.qemu import QemuConfig
    from analysis.binary_inspector import BinaryInspector
    from analysis.diagnostics import DiagnosticEngine
    from analysis.log_parser import LogParser
    
    config = load_config()
    paths = PathResolver(config.project_root)
    
    choice = choice.upper().strip()
    
    if choice == "1":
        # Build Release
        log.header("Build Release")
        builder = CargoBuilder(paths.project_root)
        validator = ArtifactValidator()
        
        # Kernel
        result = await builder.build("Kernel", paths.forge, profile="release")
        if not result.success:
            return True
        validator.validate_kernel(paths.kernel_binary())
        
        # Bootloader
        result = await builder.build("Bootloader", paths.ignite, 
                                     target="x86_64-unknown-uefi", profile="release")
        if not result.success:
            return True
        validator.validate_bootloader(paths.bootloader_binary())
        
        # Services
        for svc in config.components.services:
            svc_path = paths.services / svc.name
            await builder.build(svc.name, svc_path, target=svc.target, profile="release")
        
        # Dist
        dist_builder = DistBuilder(paths, config)
        dist_builder.prepare()
        
        initramfs_builder = InitramfsBuilder(paths, config)
        await initramfs_builder.build()
        
        log.success("Build concluído!")
        
    elif choice == "2":
        # Kernel only
        log.header("Build Kernel")
        builder = CargoBuilder(paths.project_root)
        await builder.build("Kernel", paths.forge, profile="release")
        
    elif choice == "3":
        # Bootloader only
        log.header("Build Bootloader")
        builder = CargoBuilder(paths.project_root)
        await builder.build("Bootloader", paths.ignite, 
                           target="x86_64-unknown-uefi", profile="release")
        
    elif choice == "4":
        # Services only
        log.header("Build Services")
        builder = CargoBuilder(paths.project_root)
        for svc in config.components.services:
            svc_path = paths.services / svc.name
            await builder.build(svc.name, svc_path, target=svc.target, profile="release")
        
    elif choice == "5":
        # Run QEMU
        log.header("Executando QEMU")
        qemu_config = QemuConfig(
            memory=config.qemu.memory,
            debug_flags=config.qemu.logging.flags,
        )
        
        monitor = QemuMonitor(paths, config, stop_on_exception=True, show_serial=True)
        result = await monitor.run_monitored(qemu_config)
        
        if result.crashed and result.crash_info:
            engine = DiagnosticEngine(paths, config)
            diagnosis = await engine.analyze_crash(result.crash_info)
            
            # Relatório completo com contexto serial e CPU
            serial_context = monitor.capture.get_serial_context(50)
            cpu_context = monitor.capture.get_cpu_log_context(100)
            
            engine.print_full_crash_report(
                diagnosis=diagnosis,
                crash_list=result.crash_list,
                serial_context=serial_context,
                cpu_context=cpu_context,
            )
        
    elif choice == "6":
        # Run QEMU + GDB
        log.header("Executando QEMU + GDB")
        log.info("QEMU aguardando GDB em localhost:1234")
        log.info("Para conectar: gdb -ex 'target remote :1234'")
        
        qemu_config = QemuConfig(
            memory=config.qemu.memory,
            enable_gdb=True,
        )
        
        monitor = QemuMonitor(paths, config, stop_on_exception=False)
        await monitor.run_monitored(qemu_config)
        
    elif choice == "7":
        # Analyze last log
        log.header("Analisando Log")
        
        if not paths.internal_log.exists():
            log.error("Nenhum log encontrado")
            return True
        
        parser = LogParser()
        for event in parser.parse_file(paths.internal_log):
            if event.event_type == "exception":
                console.print(f"[red]💥 {event.raw_line}[/red]")
        
        summary = parser.analyze_summary()
        console.print(f"\n[dim]Linhas: {summary['total_lines']} | "
                     f"Exceções: {summary['exceptions_count']}[/dim]")
        
    elif choice == "8":
        # Inspect kernel
        log.header("Inspecionando Kernel")
        inspector = BinaryInspector(paths)
        
        kernel = paths.kernel_binary()
        if not kernel.exists():
            log.error("Kernel não encontrado. Execute build primeiro.")
            return True
        
        violations = await inspector.check_sse_instructions(kernel)
        
        if violations:
            console.print(f"\n[red]⚠️ {len(violations)} instruções SSE/AVX encontradas:[/red]")
            for v in violations[:10]:
                console.print(f"  0x{v.address:x}: {v.instruction}")
        else:
            log.success("Nenhuma instrução SSE/AVX encontrada!")
        
        sections = await inspector.analyze_sections(kernel)
        
        table = Table(title="Seções do Kernel")
        table.add_column("Nome")
        table.add_column("Tamanho", justify="right")
        
        for sec in sections[:10]:
            table.add_row(sec.name, f"{sec.size:,}")
        
        console.print(table)
        
    elif choice == "9":
        # Code statistics
        log.header("Estatísticas de Código")
        import os
        
        total_lines = 0
        files_count = 0
        
        for root, _, files in os.walk(paths.forge / "src"):
            for file in files:
                if file.endswith(".rs"):
                    files_count += 1
                    with open(os.path.join(root, file), "r", 
                             encoding="utf-8", errors="ignore") as f:
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
        
    elif choice == "C":
        # Clean
        log.header("Limpando Artefatos")
        import shutil
        
        targets = [
            paths.forge / "target",
            paths.ignite / "target",
            paths.dist,
        ]
        
        for svc_dir in paths.services.iterdir():
            if svc_dir.is_dir():
                targets.append(svc_dir / "target")
        
        for target in targets:
            if target.exists():
                log.step(f"Removendo {paths.relative(target)}")
                shutil.rmtree(target)
        
        log.success("Limpeza concluída!")
        
    elif choice == "E":
        # Environment
        log.header("Ambiente")
        import subprocess
        
        console.print(f"\n[cyan]📂 Projeto:[/cyan] {paths.project_root}")
        
        try:
            rustc = subprocess.run(["rustc", "--version"], capture_output=True, text=True)
            console.print(f"\n[cyan]🦀 Rust:[/cyan] {rustc.stdout.strip()}")
        except FileNotFoundError:
            console.print("\n[red]Rust não encontrado[/red]")
        
        console.print(f"\n[cyan]📦 Serviços:[/cyan]")
        for svc in config.components.services:
            console.print(f"   - {svc.name}")
        
    elif choice == "Q":
        return False
    
    else:
        log.warning("Opção inválida")
    
    return True


def run_tui() -> None:
    """Executa interface TUI interativa."""
    running = True
    
    while running:
        show_menu()
        
        choice = Prompt.ask("Selecione")
        
        try:
            running = asyncio.run(handle_choice(choice))
            
            if running:
                Prompt.ask("\n[dim]Pressione Enter para continuar[/dim]")
                
        except KeyboardInterrupt:
            running = False
        except Exception as e:
            log.error(f"Erro: {e}")
            Prompt.ask("\n[dim]Pressione Enter para continuar[/dim]")
    
    console.print("\n[cyan]Até logo! 👋[/cyan]")


if __name__ == "__main__":
    run_tui()
