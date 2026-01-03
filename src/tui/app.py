"""Anvil TUI - Main Application."""

import asyncio
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
        overflow-y: auto;
        scrollbar-background: #111111;
        scrollbar-color: #333333;
        scrollbar-color-hover: #ffa500;
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
        Binding("2", "build_clean_release", "Build Clean"),
        Binding("3", "build_opt_release", "Build Opt"),
        Binding("4", "build_kernel", "Build Kernel"),
        Binding("5", "build_bootloader", "Build Bootloader"),
        Binding("6", "build_services", "Build Services"),
        Binding("a", "build_apps", "Build Apps"),
        Binding("v", "create_vdi", "Create VDI"),
        Binding("7", "run_qemu", "Run QEMU"),
        Binding("8", "run_qemu_gdb", "Run QEMU + GDB"),
        Binding("l", "listen_serial", "Listen Serial"),
        Binding("9", "analyze_log", "Analyze Log"),
        Binding("i", "inspect_kernel", "Inspect Kernel"),
        Binding("s", "statistics", "Statistics"),
        Binding("z", "clear_logs", "Clear Logs"),
        Binding("c", "clean", "Clean"),
        Binding("e", "environment", "Environment"),
        Binding("m", "toggle_menu", "Toggle Menu"),
        Binding("escape", "show_menu", "Show Menu", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.paths = Paths(self.config.project_root)
        self.log_panel = None
        
        # Setup Logger callback for TUI redirection
        from core.logger import get_logger
        self.logger = get_logger()
        self.logger._callbacks = [] # Clear any existing
        self.logger.add_callback(self._on_log_entry)
        
        # State management
        self._is_busy = False
        self._busy_lock = asyncio.Lock()
        self._last_action_time = 0.0
        self._action_cooldown = 0.3

    def _can_start_action(self) -> bool:
        import time
        now = time.time()
        if now - self._last_action_time < self._action_cooldown:
            return False
        return not self._is_busy

    async def _run_exclusive(self, action_name: str, coro_func):
        import time
        if not self._can_start_action():
            return
        
        async with self._busy_lock:
            if self._is_busy:
                return
            
            self._is_busy = True
            self._last_action_time = time.time()
            
            # Clear previous logs before starting a new action
            if self.log_panel:
                self.log_panel.clear_logs()
            
            try:
                if self.log_panel and hasattr(self.log_panel, 'log_widget'):
                    self.set_focus(self.log_panel.log_widget)
            except Exception:
                pass
            
            try:
                await coro_func()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.log_error(f"Erro em {action_name}: {e}")
            finally:
                await asyncio.sleep(0.5)
                self._is_busy = False
                self._last_action_time = time.time()

    def _on_log_entry(self, entry):
        """Redirige log entries from the central logger to the TUI panel."""
        from core.logger import LogLevel
        if not self.log_panel: return
        
        prefix = ""
        if entry.level == LogLevel.ERROR: prefix = "[bold red]✖ [/bold red]"
        elif entry.level == LogLevel.SUCCESS: prefix = "[green]✔ [/green]"
        elif entry.level == LogLevel.WARNING: prefix = "[yellow]⚠ [/yellow]"
        elif entry.level == LogLevel.DEBUG: prefix = "[dim]🔍 [/dim]"
        elif entry.level == LogLevel.INFO: prefix = "[blue]ℹ [/blue]"
        
        # Avoid double escaping if it's already structured or raw
        self.log_panel.add_log(f"{prefix}{entry.message}", is_markup=True)

    def compose(self) -> ComposeResult:
        with Horizontal(id="main_container"):
            yield MenuPanel(id="menu_panel")
            self.log_panel = LogPanel(id="log_panel")
            yield self.log_panel

    def log_info(self, msg: str):
        if self.log_panel: self.log_panel.add_log(f"[blue]ℹ {msg}[/blue]", True)

    def log_success(self, msg: str):
        if self.log_panel: self.log_panel.add_log(f"[green]✔ {msg}[/green]", True)

    def log_warning(self, msg: str):
        if self.log_panel: self.log_panel.add_log(f"[yellow]⚠ {msg}[/yellow]", True)

    def log_error(self, msg: str):
        if self.log_panel: self.log_panel.add_log(f"[bold red]✖ {msg}[/bold red]", True)

    def log_header(self, title: str):
        if self.log_panel: self.log_panel.add_log(f"\n[bold #ffa500]━━━ {title} ━━━[/bold #ffa500]", True)

    def log_raw(self, line: str):
        if self.log_panel: self.log_panel.add_raw(line)

    def log_markup(self, line: str):
        if self.log_panel: self.log_panel.add_log(line, is_markup=True)

    # Handlers
    @on(Button.Pressed, "#build_release")
    async def on_build_release(self, event: Button.Pressed): 
        event.stop(); await self._run_exclusive("Build Release", self._build_release)

    @on(Button.Pressed, "#build_clean_release")
    async def on_build_clean_release(self, event: Button.Pressed): 
        event.stop(); await self._run_exclusive("Build Clean", self._build_clean_release)

    @on(Button.Pressed, "#build_opt_release")
    async def on_build_opt_release(self, event: Button.Pressed): 
        event.stop(); await self._run_exclusive("Build Opt", self._build_opt_release)
    
    @on(Button.Pressed, "#run_qemu")
    async def on_run_qemu(self, event: Button.Pressed): 
        event.stop(); await self._run_exclusive("Run QEMU", self._run_qemu)

    @on(Button.Pressed, "#build_kernel")
    async def on_build_kernel(self, event: Button.Pressed):
        event.stop(); await self._run_exclusive("Build Kernel", self._build_kernel)

    @on(Button.Pressed, "#build_bootloader")
    async def on_build_bootloader(self, event: Button.Pressed):
        event.stop(); await self._run_exclusive("Build Bootloader", self._build_bootloader)

    @on(Button.Pressed, "#build_services")
    async def on_build_services(self, event: Button.Pressed):
        event.stop(); await self._run_exclusive("Build Services", self._build_services)

    @on(Button.Pressed, "#build_apps")
    async def on_build_apps(self, event: Button.Pressed):
        event.stop(); await self._run_exclusive("Build Apps", self._build_apps)

    @on(Button.Pressed, "#create_vdi")
    async def on_create_vdi(self, event: Button.Pressed):
        event.stop(); await self._run_exclusive("Create VDI", self._create_vdi)

    @on(Button.Pressed, "#listen_serial")
    async def on_listen_serial(self, event: Button.Pressed):
        event.stop(); await self._run_exclusive("Listen Serial", self._listen_serial)

    @on(Button.Pressed, "#analyze_log")
    async def on_analyze_log(self, event: Button.Pressed):
        event.stop(); await self._run_exclusive("Analyze Log", self._analyze_log)

    @on(Button.Pressed, "#inspect_kernel")
    async def on_inspect_kernel(self, event: Button.Pressed):
        event.stop(); await self._run_exclusive("Inspect Kernel", self._inspect_kernel)

    @on(Button.Pressed, "#statistics")
    async def on_statistics(self, event: Button.Pressed):
        event.stop(); await self._run_exclusive("Statistics", self._statistics)

    @on(Button.Pressed, "#clean")
    async def on_clean(self, event: Button.Pressed):
        event.stop(); await self._run_exclusive("Clean", self._clean)

    @on(Button.Pressed, "#environment")
    async def on_environment(self, event: Button.Pressed):
        event.stop(); await self._run_exclusive("Environment", self._environment)

    @on(Button.Pressed, "#toggle_menu")
    async def on_toggle_menu_btn(self, event: Button.Pressed):
        event.stop(); await self.action_toggle_menu()

    @on(Button.Pressed, "#copy_log")
    async def on_copy_log(self, event: Button.Pressed):
        event.stop(); await self._copy_log()

    @on(Button.Pressed, "#quit")
    async def on_quit_btn(self, event: Button.Pressed):
        event.stop(); self.exit()

    # Keyboard Actions
    async def action_build_release(self): await self._run_exclusive("Build Release", self._build_release)
    async def action_build_clean_release(self): await self._run_exclusive("Build Clean", self._build_clean_release)
    async def action_build_opt_release(self): await self._run_exclusive("Build Opt", self._build_opt_release)
    async def action_run_qemu(self): await self._run_exclusive("Run QEMU", self._run_qemu)
    async def action_toggle_menu(self):
        try:
            menu = self.query_one("#menu_panel")
            menu.display = not menu.display
        except: pass

    async def action_show_menu(self):
        """Specifically ensure the menu is visible (bound to ESC)."""
        try:
            menu = self.query_one("#menu_panel")
            menu.display = True
        except: pass

    # Build/Run logic (remained similar but simplified imports/calls if needed)
    async def _run_cargo(self, name: str, path: Path, target: str = None, profile: str = "release") -> bool:
        self.log_info(f"Construindo {name}...")
        cmd = ["cargo", "build"]
        if profile == "release": cmd.append("--release")
        elif profile != "debug": cmd.extend(["--profile", profile])
        if target: cmd.extend(["--target", target])
        try:
            process = await asyncio.create_subprocess_exec(*cmd, cwd=path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            while True:
                line = await process.stdout.readline()
                if not line: break
                decoded = line.decode("utf-8", errors="replace").rstrip()
                if decoded: self.log_raw(decoded)
            await process.wait()
            if process.returncode == 0:
                self.log_success(f"{name} pronto!")
                return True
            self.log_error(f"Erro em {name}!")
            return False
        except Exception as e:
            self.log_error(f"Erro: {e}")
            return False

    async def _build_release(self):
        """Build everything using the standard 'release' profile."""
        from build.dist import DistBuilder
        from build.initramfs import InitramfsBuilder
        self.log_header("Build Total (Release)")
        
        # Build Kernel, Bootloader, Services and Apps with 'release'
        if not await self._run_cargo("Kernel", self.paths.forge, profile="release"): return
        if not await self._run_cargo("Bootloader", self.paths.ignite, target="x86_64-unknown-uefi", profile="release"): return
        
        for svc in self.config.components.services:
            if not await self._run_cargo(svc.name, self.paths.root / svc.path, target=svc.target, profile="release"): return
            
        for app in self.config.components.apps:
            if not await self._run_cargo(app.name, self.paths.root / app.path, target=app.target, profile="release"): return
            
        DistBuilder(self.paths, self.config).prepare(profile="release")
        await InitramfsBuilder(self.paths, self.config).build(profile="release")
        self.log_success("Build Release concluída!")

    async def _build_clean_release(self):
        """Build with 'clean-release' for the Kernel and 'release' for the rest."""
        from build.dist import DistBuilder
        from build.initramfs import InitramfsBuilder
        self.log_header("Build Limpa (Zero Tracer)")
        
        # Kernel use 'clean-release'
        if not await self._run_cargo("Kernel", self.paths.forge, profile="clean-release"): return
        
        # Rest uses 'release'
        if not await self._run_cargo("Bootloader", self.paths.ignite, target="x86_64-unknown-uefi", profile="release"): return
        
        for svc in self.config.components.services:
            if not await self._run_cargo(svc.name, self.paths.root / svc.path, target=svc.target, profile="release"): return
            
        for app in self.config.components.apps:
            if not await self._run_cargo(app.name, self.paths.root / app.path, target=app.target, profile="release"): return
            
        # We need to explicitly point to where artifacts are
        # DistBuilder and InitramfsBuilder take profile names to find binaries
        # Since we mix them, cleaner approach: they use 'release' for most, but we handle kernel specially
        
        # We tell builders to prepared from 'release', but then 'DistBuilder' will be cheated
        # if we copy the kernel manually.
        import shutil
        self.log_info("Deploying clean artifacts...")
        shutil.copy2(self.paths.kernel_binary("clean-release"), self.paths.kernel_binary("release"))
        
        DistBuilder(self.paths, self.config).prepare(profile="release")
        await InitramfsBuilder(self.paths, self.config).build(profile="release")
        self.log_success("Build Limpa concluída!")

    async def _build_opt_release(self):
        """Build everything using the 'opt-release' production profile."""
        from build.dist import DistBuilder
        from build.initramfs import InitramfsBuilder
        self.log_header("Build Otimizada (PRODUÇÃO)")
        
        if not await self._run_cargo("Kernel", self.paths.forge, profile="opt-release"): return
        if not await self._run_cargo("Bootloader", self.paths.ignite, target="x86_64-unknown-uefi", profile="opt-release"): return
        
        for svc in self.config.components.services:
            if not await self._run_cargo(svc.name, self.paths.root / svc.path, target=svc.target, profile="opt-release"): return
            
        for app in self.config.components.apps:
            if not await self._run_cargo(app.name, self.paths.root / app.path, target=app.target, profile="opt-release"): return
            
        DistBuilder(self.paths, self.config).prepare(profile="opt-release")
        await InitramfsBuilder(self.paths, self.config).build(profile="opt-release")
        self.log_success("Build Otimizada concluída!")

    async def _build_kernel(self): await self._run_cargo("Kernel", self.paths.forge)
    async def _build_bootloader(self): await self._run_cargo("Bootloader", self.paths.ignite, target="x86_64-unknown-uefi")
    async def _build_services(self):
        for svc in self.config.components.services: await self._run_cargo(svc.name, self.paths.root / svc.path, target=svc.target)
    async def _build_apps(self):
        for app in self.config.components.apps: await self._run_cargo(app.name, self.paths.root / app.path, target=app.target)
    
    async def _create_vdi(self):
        from build.image import ImageBuilder
        builder = ImageBuilder(self.paths, self.config, log=self.logger)
        await builder.build_vdi(profile="release")

    async def _run_qemu(self, gdb=False):
        from runner.monitor import QemuMonitor
        from runner.qemu import QemuConfig
        self.log_header("QEMU Start")
        try:
            cfg = QemuConfig(memory=self.config.qemu.memory, debug_flags=self.config.qemu.logging.flags, enable_gdb=gdb)
            monitor = QemuMonitor(self.paths, self.config, stop_on_exception=True, show_serial=False)
            from runner.streams import StreamSource
            monitor.capture.add_callback(lambda e: self.log_raw(e.line) if e.source == StreamSource.SERIAL else None)
            result = await monitor.run_monitored(cfg)
            if result.crashed: self.log_error(f"CRASH: {result.crash_info}")
        finally: self.log_header("QEMU End")

    async def _run_qemu_gdb(self): await self._run_qemu(gdb=True)

    async def _listen_serial(self):
        from runner.serial import PipeListener
        
        # Função segura para ser chamada de fora da thread principal
        def thread_safe_log(line):
            self.call_from_thread(self.log_raw, line)
            
        listener = PipeListener(r"\\.\pipe\VBoxCom1", on_line=thread_safe_log)
        await listener.start()

    async def _analyze_log(self):
        from analysis.parser import LogParser
        log_path = self.paths.cpu_log
        if log_path.exists():
            parser = LogParser()
            for event in parser.parse_file(log_path):
                if event.event_type == "exception": self.log_error(f"Exceção: {event.raw_line[:80]}")
            self.log_info(f"Análise OK")
        else: self.log_warning("Log não achado")

    async def _inspect_kernel(self):
        from analysis.inspector import BinaryInspector
        violations = await BinaryInspector(self.paths).check_sse(self.paths.kernel_binary())
        if violations: self.log_warning(f"{len(violations)} SSE!")
        else: self.log_success("Kernel limpo")

    async def _statistics(self):
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
                        t_files += 1
                        in_block = False
                        for line in f:
                            t_lines += 1
                            s = line.strip()
                            if not s: continue
                            
                            if in_block:
                                if "*/" in s:
                                    in_block = False
                                    s = s.split("*/", 1)[1].strip()
                                    if not s: continue
                                else: continue
                            
                            if s.startswith("/*"):
                                if "*/" in s:
                                    s = s.split("*/", 1)[1].strip()
                                    if not s: continue
                                else:
                                    in_block = True
                                    continue
                            
                            if s.startswith("//") or not s:
                                continue
                            
                            t_code += 1
                except: pass
            return t_files, t_lines, t_code

        def scan_crates(base_path: Path) -> tuple[int, int, int]:
            """Scan all subdirectories that are rust crates."""
            t_f, t_l, t_c = 0, 0, 0
            if not base_path.exists(): return 0, 0, 0
            for item in base_path.iterdir():
                if item.is_dir() and ((item / "Cargo.toml").exists() or (item / "src").exists()):
                    f, l, c = count_path(item)
                    t_f += f; t_l += l; t_c += c
            return t_f, t_l, t_c

        # Define categories
        items = [
            ("Kernel", self.paths.forge),
            ("Bootloader", self.paths.ignite),
            ("Compositor", self.paths.root / "firefly" / "compositor"),
            ("Shell", self.paths.root / "firefly" / "shell"),
        ]
        
        groups = [
            ("Serviços", self.paths.services),
            ("Apps", self.paths.root / "firefly" / "apps"),
            ("Bibliotecas", self.paths.lib),
            ("SDK", self.paths.sdk),
        ]

        grand_files = 0
        grand_code = 0

        self.log_markup(f"[bold]{'Componente':<20} | {'Arquivos':<10} | {'Linhas':<15}[/bold]")
        self.log_markup("-" * 55)

        for name, path in items:
            f, l, c = count_path(path)
            if f > 0:
                self.log_markup(f"{name:<20} | {f:<10} | [bold green]{c:<15,}[/bold green]")
                grand_files += f; grand_code += c

        for name, path in groups:
            f, l, c = scan_crates(path)
            if f > 0:
                self.log_markup(f"{name:<20} | {f:<10} | [bold green]{c:<15,}[/bold green]")
                grand_files += f; grand_code += c

        self.log_markup("-" * 55)
        self.log_markup(f"[bold cyan]{'TOTAL':<20} | {grand_files:<10} | {grand_code:<15,}[/bold cyan]")
        self.log_success("Análise concluída.")

    async def _clean(self):
        import shutil
        for p in [self.paths.forge/"target", self.paths.ignite/"target", self.paths.dist]:
            if p.exists(): shutil.rmtree(p)
        self.log_success("Limpo!")

    async def _copy_log(self):
        import subprocess
        if not self.log_panel: return
        text = self.log_panel.get_plain_text()
        process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
        process.communicate(text.encode('utf-8'))
        self.log_success("Copiado!")

    async def _environment(self):
        self.log_header("Environment")
        self.log_info(f"Root: {self.paths.root}")
        self.log_info(f"Services: {len(self.config.components.services)}")
