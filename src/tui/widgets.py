from datetime import datetime
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, RichLog, Button
from runner.serial import SerialColorizer

class MenuPanel(Static):
    """Sidebar menu panel."""

    def compose(self) -> ComposeResult:
        yield Static("[bold #ffa500]⚡ Redstone[/bold #ffa500][bold white]OS[/bold white]\n", classes="menu-title")

        yield Button("Release Total", id="build_release", classes="menu-btn")
        yield Button("Release Otimizado", id="build_opt_release", classes="menu-btn")
        yield Button("Apenas Kernel", id="build_kernel", classes="menu-btn")
        yield Button("Bootloader", id="build_bootloader", classes="menu-btn")
        yield Button("Serviços", id="build_services", classes="menu-btn")
        yield Button("Apps", id="build_apps", classes="menu-btn")
        yield Button("Imagem VDI", id="create_vdi", classes="menu-btn")
        yield Button("QEMU Normal", id="run_qemu", classes="menu-btn")
        yield Button("QEMU + GDB", id="run_qemu_gdb", classes="menu-btn")
        yield Button("Monitor Serial", id="listen_serial", classes="menu-btn")
        yield Button("Analisar Log", id="analyze_log", classes="menu-btn")
        yield Button("Inspecionar SSE", id="inspect_kernel", classes="menu-btn")
        yield Button("Estatísticas", id="statistics", classes="menu-btn")
        yield Button("Limpar Logs", id="clear_logs", classes="menu-btn")
        yield Button("Limpar Build", id="clean", classes="menu-btn")
        yield Button("Ambiente", id="environment", classes="menu-btn")
        yield Button("Tela Cheia", id="toggle_menu", classes="menu-btn")
        yield Button("Sair", id="quit", classes="menu-btn-quit")


class LogPanel(Static):
    """Log display panel."""

    def compose(self) -> ComposeResult:
        self.log_widget = RichLog(highlight=True, markup=True, auto_scroll=True, max_lines=10000)
        self.log_widget.can_focus = True
        yield self.log_widget

    def add_log(self, message: str, is_markup: bool = False):
        """Add a log line."""
        if not hasattr(self, 'log_widget') or not self.log_widget:
            return

        ts = datetime.now().strftime("%H:%M:%S")

        if is_markup:
            content = message
        else:
            # Escape Rich markup
            content = message.replace("[", "\\[")

        self.log_widget.write(content)

    def add_raw(self, line: str):
        """Add raw line (with colorization)."""
        if hasattr(self, 'log_widget') and self.log_widget:
            # 1. Apply serial colorization if it contains typical log markers
            markers = ["[OK]", "[INFO]", "[TRACE]", "[DEBUG]", "[ERROR]", "[WARN]", "[FAIL]", 
                       "[Supervisor]", "[Compositor]", "[Shell]", "[Input]"]
            
            if any(marker in line for marker in markers):
                line = SerialColorizer.colorize(line)
                is_markup = True
            else:
                # 2. Apply general patterns (Cargo, etc)
                is_markup = False
                original_line = line
                
                if "error" in line.lower():
                    line = f"[bold red]{line}[/bold red]"
                    is_markup = True
                elif "warning" in line.lower():
                    line = f"[yellow]{line}[/yellow]"
                    is_markup = True
                elif "Compiling" in line:
                    line = f"[cyan]{line}[/cyan]"
                    is_markup = True
                elif "Finished" in line:
                    line = f"[bold green]{line}[/bold green]"
                    is_markup = True
                elif "Building" in line:
                    line = f"[blue]{line}[/blue]"
                    is_markup = True
                
                # Escape brackets if not already marked up by SerialColorizer
                # (Simple heuristic: if it doesn't have [color] tags)
                if not is_markup and "[" in line:
                   line = line.replace("[", "\\[")
                   
            if is_markup:
                 self.log_widget.write(line)
            else:
                 # If no markup was applied, we still need to write it safely (escaped above or naturally safe)
                 self.log_widget.write(line)

    def clear_logs(self):
        """Clear all logs."""
        if hasattr(self, 'log_widget') and self.log_widget:
            self.log_widget.clear()
