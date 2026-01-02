import asyncio
import os
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button
from textual.binding import Binding
from textual import on

from core.config import load_config
from core.paths import Paths
from .widgets import MenuPanel, LogPanel

class AnvilApp(App):
    """Main Anvil TUI application."""

    CSS = """
    Screen {
        background: #0a0a0a;
        color: #e0e0e0;
    }

    #main_container {
        width: 100%;
        height: 100%;
    }

    #menu_panel {
        width: 28;
        height: 100%;
        background: #111111;
        border-right: solid #333333;
        padding: 1 1;
    }

    .menu-title {
        text-align: center;
        margin-bottom: 1;
        color: #ffa500;
        text-style: bold;
    }

    .category {
        margin-top: 1;
        margin-bottom: 0;
        padding-left: 1;
        color: #555555;
        text-align: left;
    }

    .menu-btn {
        width: 100%;
        height: 3;
        background: transparent;
        border: round #333333;
        color: #888888;
        padding: 0 1;
        margin-bottom: 0;
        content-align: left middle;
    }

    .menu-btn:hover {
        background: transparent;
        color: #ffa500;
        border: round #ffa500;
    }

    .menu-btn:focus {
        background: #1a1a1a 10%;
        text-style: bold;
    }

    .menu-btn-quit {
        width: 100%;
        height: 3;
        background: transparent;
        border: round #441111;
        color: #ff4444;
        padding: 0 1;
        margin-top: 1;
        content-align: left middle;
    }

    .menu-btn-quit:hover {
        background: transparent;
        color: #ff0000;
        border: round #ff0000;
    }

    #log_panel {
        width: 1fr;
        height: 100%;
        background: #0a0a0a;
        border: solid #333333;
        padding: 0 1;
    }

    RichLog {
        background: #0a0a0a;
        color: #e0e0e0;
        border: solid #222222;
        scrollbar-background: #111111;
        scrollbar-color: #333333;
        scrollbar-color-hover: #ffa500;
    }

    RichLog:focus {
        border: double #ffa500;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("1", "build_release", "Build Release"),
        Binding("2", "build_kernel", "Build Kernel"),
        Binding("3", "build_bootloader", "Build Bootloader"),
        Binding("4", "build_services", "Build Services"),
        Binding("a", "build_apps", "Build Apps"),
        Binding("v", "create_vdi", "Create VDI"),
        Binding("5", "run_qemu", "Run QEMU"),
        Binding("6", "run_qemu_gdb", "Run QEMU + GDB"),
        Binding("l", "listen_serial", "Listen Serial"),
        Binding("7", "analyze_log", "Analyze Log"),
        Binding("8", "inspect_kernel", "Inspect Kernel"),
        Binding("9", "statistics", "Statistics"),
        Binding("z", "clear_logs", "Clear Logs"),
        Binding("c", "clean", "Clean"),
        Binding("e", "environment", "Environment"),
        Binding("m", "toggle_menu", "Toggle Menu"),
    ]

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.paths = Paths(self.config.project_root)
        self.log_panel = None
        self._qemu_running = False  # Guard to prevent multiple QEMU instances

    def compose(self) -> ComposeResult:
        """Create the layout."""
        with Horizontal(id="main_container"):
            yield MenuPanel(id="menu_panel")
            self.log_panel = LogPanel(id="log_panel")
            yield self.log_panel

    def log_info(self, msg: str):
        if self.log_panel:
            self.log_panel.add_log(f"[cyan]ℹ {msg}[/cyan]", True)

    def log_success(self, msg: str):
        if self.log_panel:
            self.log_panel.add_log(f"[green]✔ {msg}[/green]", True)

    def log_warning(self, msg: str):
        if self.log_panel:
            self.log_panel.add_log(f"[yellow]⚠ {msg}[/yellow]", True)

    def log_error(self, msg: str):
        if self.log_panel:
            self.log_panel.add_log(f"[bold red]✖ {msg}[/bold red]", True)

    def log_header(self, title: str):
        if self.log_panel:
            self.log_panel.add_log(f"\n[bold #ffa500]━━━ {title} ━━━[/bold #ffa500]", True)

    def log_raw(self, line: str):
        if self.log_panel:
            self.log_panel.add_raw(line)

    # --- Button Click Handlers ---
    @on(Button.Pressed, "#build_release")
    async def on_build_release(self): await self._build_release()
    
    @on(Button.Pressed, "#build_opt_release")
    async def on_build_opt_release(self): await self._build_opt_release()
    
    @on(Button.Pressed, "#build_kernel")
    async def on_build_kernel(self): await self._build_kernel()
    
    @on(Button.Pressed, "#build_bootloader")
    async def on_build_bootloader(self): await self._build_bootloader()
    
    @on(Button.Pressed, "#build_services")
    async def on_build_services(self): await self._build_services()

    @on(Button.Pressed, "#build_apps")
    async def on_build_apps(self): await self._build_apps()
    
    @on(Button.Pressed, "#create_vdi")
    async def on_create_vdi(self): await self._create_vdi()
    
    @on(Button.Pressed, "#run_qemu")
    async def on_run_qemu(self): await self._run_qemu()
    
    @on(Button.Pressed, "#run_qemu_gdb")
    async def on_run_qemu_gdb(self): await self._run_qemu_gdb()
    
    @on(Button.Pressed, "#listen_serial")
    async def on_listen_serial(self): await self._listen_serial()
    
    @on(Button.Pressed, "#analyze_log")
    async def on_analyze_log(self): await self._analyze_log()
    
    @on(Button.Pressed, "#inspect_kernel")
    async def on_inspect_kernel(self): await self._inspect_kernel()
    
    @on(Button.Pressed, "#statistics")
    async def on_statistics(self): await self._statistics()
    
    @on(Button.Pressed, "#clear_logs")
    async def on_clear_logs(self):
        if self.log_panel:
            self.log_panel.clear_logs()
            self.log_success("Logs limpos.")
    
    @on(Button.Pressed, "#clean")
    async def on_clean(self): await self._clean()
    
    @on(Button.Pressed, "#environment")
    async def on_environment(self): await self._environment()

    @on(Button.Pressed, "#toggle_menu")
    async def on_toggle_menu_btn(self): await self.action_toggle_menu()
    
    @on(Button.Pressed, "#quit")
    async def on_quit_btn(self): self.exit()

    # --- Keyboard Actions ---
    async def action_build_release(self): await self._build_release()
    async def action_build_kernel(self): await self._build_kernel()
    async def action_build_bootloader(self): await self._build_bootloader()
    async def action_build_services(self): await self._build_services()
    async def action_build_apps(self): await self._build_apps()
    async def action_create_vdi(self): await self._create_vdi()
    async def action_run_qemu(self): await self._run_qemu()
    async def action_run_qemu_gdb(self): await self._run_qemu_gdb()
    async def action_listen_serial(self): await self._listen_serial()
    async def action_analyze_log(self): await self._analyze_log()
    async def action_inspect_kernel(self): await self._inspect_kernel()
    async def action_statistics(self): await self._statistics()
    async def action_clear_logs(self):
        if self.log_panel:
            self.log_panel.clear_logs()
            self.log_success("Logs cleared.")
    async def action_clean(self): await self._clean()
    async def action_environment(self): await self._environment()

    async def action_toggle_menu(self):
        """Toggle the menu panel visibility."""
        try:
            menu = self.query_one("#menu_panel")
            menu.display = not menu.display
            if menu.display:
                self.log_info("Menu visível.")
            else:
                self.log_info("Menu oculto (Modo Tela Cheia). Seleção de texto facilitada.")
        except Exception:
            pass

    # --- Cargo Build with Full Output ---
    async def _run_cargo(self, name: str, path: Path, target: str = None, profile: str = "release") -> bool:
        """Run cargo build with streaming output."""
        self.log_info(f"Construindo {name}...")
        
        cmd = ["cargo", "build"]
        if profile == "release":
            cmd.append("--release")
        elif profile != "debug":
            cmd.extend(["--profile", profile])
            
        if target:
            cmd.extend(["--target", target])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip()
                if decoded:
                    self.log_raw(decoded)
            
            await process.wait()
            
            if process.returncode == 0:
                self.log_success(f"{name} construído com sucesso!")
                return True
            else:
                self.log_error(f"Erro na build de {name}!")
                return False
        except Exception as e:
            self.log_error(f"Erro de build: {e}")
            return False

    # --- Build Actions ---
    async def _build_release(self):
        from build.dist import DistBuilder
        from build.initramfs import InitramfsBuilder
        
        self.log_panel.clear_logs()
        self.log_header("Build da Release Total")
        
        # Kernel
        if not await self._run_cargo("Kernel", self.paths.forge):
            return
        
        # Bootloader
        if not await self._run_cargo("Bootloader", self.paths.ignite, target="x86_64-unknown-uefi"):
            return
        
        # Services
        for svc in self.config.components.services:
            await self._run_cargo(svc.name, self.paths.root / svc.path, target=svc.target)

        # Apps
        for app in self.config.components.apps:
            await self._run_cargo(app.name, self.paths.root / app.path, target=app.target)
        
        # Dist preparation
        self.log_info("Preparando distribuição...")
        DistBuilder(self.paths, self.config).prepare()
        self.log_success("dist/qemu pronta")
        
        # Initramfs
        self.log_info("Construindo initramfs...")
        await InitramfsBuilder(self.paths, self.config).build()
        
        self.log_success("Build concluída com sucesso!")

    async def _build_opt_release(self):
        from build.dist import DistBuilder
        from build.initramfs import InitramfsBuilder
        
        self.log_panel.clear_logs()
        self.log_header("Build da Release Otimizada")
        
        # Kernel
        if not await self._run_cargo("Kernel", self.paths.forge, profile="opt-release"):
            return
        
        # Bootloader
        if not await self._run_cargo("Bootloader", self.paths.ignite, target="x86_64-unknown-uefi", profile="opt-release"):
            return
        
        # Services
        for svc in self.config.components.services:
            await self._run_cargo(svc.name, self.paths.root / svc.path, target=svc.target, profile="opt-release")

        # Apps
        for app in self.config.components.apps:
            await self._run_cargo(app.name, self.paths.root / app.path, target=app.target, profile="opt-release")
        
        # Dist preparation
        self.log_info("Preparando distribuição...")
        DistBuilder(self.paths, self.config).prepare(profile="opt-release")
        self.log_success("dist/qemu pronta")
        
        # Initramfs
        self.log_info("Construindo initramfs...")
        await InitramfsBuilder(self.paths, self.config).build(profile="opt-release")
        
        self.log_success("Build Otimizada concluída com sucesso!")

    async def _build_kernel(self):
        self.log_panel.clear_logs()
        self.log_header("Build do Kernel")
        await self._run_cargo("Kernel", self.paths.forge)

    async def _build_bootloader(self):
        self.log_panel.clear_logs()
        self.log_header("Build do Bootloader")
        await self._run_cargo("Bootloader", self.paths.ignite, target="x86_64-unknown-uefi")

    async def _build_services(self):
        self.log_panel.clear_logs()
        self.log_header("Build dos Serviços")
        for svc in self.config.components.services:
            await self._run_cargo(svc.name, self.paths.root / svc.path, target=svc.target)

    async def _build_apps(self):
        self.log_panel.clear_logs()
        self.log_header("Build dos Apps")
        for app in self.config.components.apps:
            await self._run_cargo(app.name, self.paths.root / app.path, target=app.target)

    async def _create_vdi(self):
        from build.image import ImageBuilder
        self.log_panel.clear_logs()
        self.log_header("Criando Imagem VDI")
        try:
            await ImageBuilder(self.paths, self.config).build_vdi(profile="release")
            self.log_success("VDI criada com sucesso!")
        except Exception as e:
            self.log_error(f"Falha na criação da VDI: {e}")

    # --- Run Actions ---
    async def _run_qemu(self):
        if self._qemu_running:
            self.log_warning("QEMU já está rodando.")
            return

        from runner.monitor import QemuMonitor
        from runner.qemu import QemuConfig
        
        self.log_panel.clear_logs()
        self.log_header("Iniciando QEMU")
        self._qemu_running = True
        
        # 1. Remove focus from button to prevent accidental re-trigger
        if self.log_panel:
            self.set_focus(self.log_panel)

        # 2. Cooldown start
        await asyncio.sleep(0.5)
        
        try:
            qemu_config = QemuConfig(memory=self.config.qemu.memory, debug_flags=self.config.qemu.logging.flags)
            
            monitor = QemuMonitor(self.paths, self.config, stop_on_exception=True, show_serial=False)
            
            # Custom callback to show serial in TUI
            from runner.streams import StreamSource
            def on_line(entry):
                if entry.source == StreamSource.SERIAL:
                    self.log_raw(entry.line)
            
            monitor.capture.add_callback(on_line)
            
            result = await monitor.run_monitored(qemu_config)
            
            if result.crashed and result.crash_info:
                self.log_error(f"💥 CRASH: {result.crash_info.exception_type}")
        finally:
            self.log_header("QEMU Finalizado")
            # 3. Post-run cooldown: keep flag True for a second to absorb buffered inputs
            await asyncio.sleep(1.0)
            self._qemu_running = False

    async def _run_qemu_gdb(self):
        from runner.monitor import QemuMonitor
        from runner.qemu import QemuConfig
        
        self.log_panel.clear_logs()
        self.log_header("Iniciando QEMU com GDB")
        self.log_info("Conecte o depurador em localhost:1234")
        
        qemu_config = QemuConfig(memory=self.config.qemu.memory, enable_gdb=True)
        await QemuMonitor(self.paths, self.config, stop_on_exception=False).run_monitored(qemu_config)

    async def _listen_serial(self):
        self.log_panel.clear_logs()
        self.log_header("Monitor Serial")
        pipe_path = r"\\.\pipe\VBoxCom1"
        self.log_info(f"Escutando: {pipe_path}")
        self.log_warning("Pressione Ctrl+C para parar (no terminal)")
        
        from runner.serial import PipeListener
        await PipeListener(pipe_path).start()

    # --- Analysis Actions ---
    async def _analyze_log(self):
        from analysis.parser import LogParser
        self.log_panel.clear_logs()
        self.log_header("Análise de Log")
        log_path = self.paths.cpu_log
        if log_path.exists():
            parser = LogParser()
            for event in parser.parse_file(log_path):
                if event.event_type == "exception":
                    self.log_error(f"Exceção: {event.raw_line[:80]}")
            summary = parser.summary()
            self.log_info(f"Total de linhas: {summary.get('total_lines', 0)}")
            self.log_info(f"Exceções: {summary.get('exceptions_count', 0)}")
        else:
            self.log_warning("Nenhum arquivo de log encontrado.")

    async def _inspect_kernel(self):
        from analysis.inspector import BinaryInspector
        self.log_panel.clear_logs()
        self.log_header("Inspeção SSE do Kernel")
        kernel = self.paths.kernel_binary()
        if not kernel.exists():
            self.log_error(f"Kernel não encontrado: {kernel}")
            return
        
        violations = await BinaryInspector(self.paths).check_sse(kernel)
        if violations:
            self.log_warning(f"Encontradas {len(violations)} instruções SSE/AVX!")
            for v in violations[:10]:
                self.log_raw(f"  0x{v.address:x}: {v.instruction}")
        else:
            self.log_success("Kernel limpo (Sem SSE/AVX).")

    def log_markup(self, line: str):
        """Log a line with direct markup support (bypassing sanitization)."""
        if self.log_panel:
            self.log_panel.add_log(line, is_markup=True)

    async def _statistics(self):
        """Calculate project code statistics with detailed breakdown."""
        import os
        
        self.log_panel.clear_logs()
        self.log_header("Estatísticas do Projeto")
        self.log_info("Analisando código fonte...")
        
        def count_path(path: Path) -> tuple[int, int, int]:
            """Returns (files, total_lines, code_lines)."""
            t_files, t_lines, t_code = 0, 0, 0
            if not path.exists():
                return 0, 0, 0
                
            for p in path.rglob("*.rs"):
                if "target" in p.parts: continue
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        t_files += 1
                        t_lines += len(lines)
                        # Simple naive code count (not empty, not starting with //)
                        code = [l for l in lines if l.strip() and not l.strip().startswith("//")]
                        t_code += len(code)
                except: pass
            return t_files, t_lines, t_code

        # Define categories to analyze
        categories = [
            ("Kernel", self.paths.forge),
            ("Bootloader", self.paths.ignite),
        ]
        
        # Add Services
        services_stats = [0, 0, 0]
        for svc in self.config.components.services:
            f, l, c = count_path(self.paths.root / svc.path)
            services_stats[0] += f
            services_stats[1] += l
            services_stats[2] += c
        
        # Add Apps
        apps_stats = [0, 0, 0]
        for app in self.config.components.apps:
            f, l, c = count_path(self.paths.root / app.path)
            apps_stats[0] += f
            apps_stats[1] += l
            apps_stats[2] += c

        grand_total_files = 0
        grand_total_code = 0

        # Display Header
        self.log_markup(f"{'Componente':<20} | {'Arquivos':<10} | {'Linhas Totais':<15} | {'Código Real':<15}")
        self.log_markup("-" * 70)

        # Process main categories
        for name, path in categories:
            f, l, c = count_path(path)
            self.log_markup(f"{name:<20} | {f:<10} | {l:<15,} | [bold green]{c:<15,}[/bold green]")
            grand_total_files += f
            grand_total_code += c

        # Display Aggregated Categories
        self.log_markup(f"{'Services (Total)':<20} | {services_stats[0]:<10} | {services_stats[1]:<15,} | [bold green]{services_stats[2]:<15,}[/bold green]")
        grand_total_files += services_stats[0]
        grand_total_code += services_stats[2]

        self.log_markup(f"{'Apps (Total)':<20} | {apps_stats[0]:<10} | {apps_stats[1]:<15,} | [bold green]{apps_stats[2]:<15,}[/bold green]")
        grand_total_files += apps_stats[0]
        grand_total_code += apps_stats[2]

        self.log_markup("-" * 70)
        self.log_markup(f"{'TOTAL':<20} | {grand_total_files:<10} | {'-':<15} | [bold cyan]{grand_total_code:<15,}[/bold cyan]")
        
        self.log_success("Análise concluída.")


    async def _clean(self):
        import shutil
        self.log_panel.clear_logs()
        self.log_header("Limpando Artefatos de Build")
        
        targets = [
            (self.paths.forge / "target", "forge/target"),
            (self.paths.ignite / "target", "ignite/target"),
            (self.paths.dist, "dist"),
        ]
        
        for path, name in targets:
            if path.exists():
                shutil.rmtree(path)
                self.log_info(f"Removido: {name}")
        
        self.log_success("Limpeza concluída!")

    async def _environment(self):
        import subprocess
        
        self.log_panel.clear_logs()
        self.log_header("Informações do Ambiente")
        self.log_info(f"Projeto: {self.paths.root}")
        self.log_info(f"Kernel:  {self.paths.forge}")
        self.log_info(f"Boot:    {self.paths.ignite}")
        
        try:
            rustc = subprocess.run(["rustc", "--version"], capture_output=True, text=True)
            self.log_info(f"Rust:    {rustc.stdout.strip()}")
        except:
            self.log_warning("Rust não encontrado")
        
        self.log_info(f"Serviços: {len(self.config.components.services)}")
        for svc in self.config.components.services:
            self.log_raw(f"  - {svc.name}")

        self.log_info(f"Apps:     {len(self.config.components.apps)}")
        for app in self.config.components.apps:
            self.log_raw(f"  - {app.name}")
