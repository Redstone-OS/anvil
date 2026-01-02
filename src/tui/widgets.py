"""Anvil TUI - Widgets."""

from datetime import datetime
from typing import Optional
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, RichLog, Button
from textual.binding import Binding
from textual.events import Key
from runner.serial import SerialColorizer
import re


class MenuPanel(Static):
    """Sidebar menu panel."""

    def compose(self) -> ComposeResult:
        yield Static("[bold #ffa500]⚡ Redstone[/bold #ffa500][bold white]OS[/bold white]\n", classes="menu-title")

        # Build section
        yield Static("[dim]─── Build ───[/dim]", classes="category")
        yield Button("Release", id="build_release", classes="menu-btn")
        yield Button("Release Limpo", id="build_clean_release", classes="menu-btn")
        yield Button("Release Otimizado", id="build_opt_release", classes="menu-btn")
        yield Button("Kernel", id="build_kernel", classes="menu-btn")
        yield Button("Bootloader", id="build_bootloader", classes="menu-btn")
        yield Button("Serviços", id="build_services", classes="menu-btn")
        yield Button("Apps", id="build_apps", classes="menu-btn")
        yield Button("Gerar VDI", id="create_vdi", classes="menu-btn")
        
        # Run section
        yield Static("[dim]─── Execute ───[/dim]", classes="category")
        yield Button("QEMU", id="run_qemu", classes="menu-btn")
        yield Button("Monitor Serial", id="listen_serial", classes="menu-btn")
        
        # Analysis section
        yield Static("[dim]─── Análise ───[/dim]", classes="category")
        yield Button("Analisar Log", id="analyze_log", classes="menu-btn")
        yield Button("Inspecionar SSE", id="inspect_kernel", classes="menu-btn")
        yield Button("Estatísticas", id="statistics", classes="menu-btn")
        
        # Utility section
        yield Static("[dim]─── Util ───[/dim]", classes="category")
        yield Button("Limpar Build", id="clean", classes="menu-btn")
        yield Button("Ambiente", id="environment", classes="menu-btn")
        yield Button("Tela Cheia", id="toggle_menu", classes="menu-btn")
        yield Button("Copiar Log", id="copy_log", classes="menu-btn")
        yield Button("Sair", id="quit", classes="menu-btn-quit")


class LogPanel(Static):
    """Log display panel with colorization."""
    
    is_focused: bool = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._log_lines: list[str] = []

    def compose(self) -> ComposeResult:
        self.log_widget = RichLog(highlight=True, markup=True, auto_scroll=True, max_lines=10000)
        self.log_widget.can_focus = True
        yield self.log_widget
    
    def on_focus(self, event) -> None:
        self.is_focused = True
        self.add_class("focused")
    
    def on_blur(self, event) -> None:
        self.is_focused = False
        self.remove_class("focused")
    
    def on_key(self, event: Key) -> None:
        if event.key == "ctrl+c" and self.is_focused:
            self.copy_to_clipboard()
            event.prevent_default()
            event.stop()
    
    def copy_to_clipboard(self) -> None:
        import subprocess
        try:
            text = self.get_plain_text()
            process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
            process.communicate(text.encode('utf-8'))
            self.app.notify("📋 Log copiado!", severity="information")
        except Exception as e:
            self.app.notify(f"❌ Erro ao copiar: {e}", severity="error")
    
    def get_plain_text(self) -> str:
        return "\n".join(self._log_lines)
    
    def _strip_markup(self, text: str) -> str:
        return re.sub(r'\[/?[^\]]+\]', '', text)

    def add_log(self, message: str, is_markup: bool = False):
        if not hasattr(self, 'log_widget') or not self.log_widget: return
        if is_markup:
            content = message
            self._log_lines.append(self._strip_markup(message))
        else:
            content = message.replace("[", "\\[")
            self._log_lines.append(message)
        self.log_widget.write(content)

    def add_raw(self, line: str):
        if not hasattr(self, 'log_widget') or not self.log_widget: return
        self._log_lines.append(line)
        
        markers = ["[OK]", "[INFO]", "[TRACE]", "[DEBUG]", "[ERROR]", "[WARN]", "[FAIL]", 
                   "[Supervisor]", "[Compositor]", "[Shell]", "[Input]", "[Kernel]",
                   "[MM]", "[Heap]", "[FS]", "[Scheduler]", "[JUMP]"]
        
        if any(marker in line for marker in markers):
            line = SerialColorizer.colorize(line)
            self.log_widget.write(line)
        else:
            is_markup = False
            if "error" in line.lower():
                line = f"[bold red]{line}[/bold red]"; is_markup = True
            elif "warning" in line.lower():
                line = f"[yellow]{line}[/yellow]"; is_markup = True
            elif "Compiling" in line:
                line = f"[cyan]{line}[/cyan]"; is_markup = True
            elif "Finished" in line:
                line = f"[bold green]{line}[/bold green]"; is_markup = True
            
            if not is_markup and "[" in line:
                line = line.replace("[", "\\[")
            self.log_widget.write(line)

    def clear_logs(self):
        if hasattr(self, 'log_widget') and self.log_widget: self.log_widget.clear()
        self._log_lines = []
