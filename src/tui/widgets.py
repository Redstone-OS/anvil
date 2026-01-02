from datetime import datetime
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

        yield Button("Release", id="build_release", classes="menu-btn")
        yield Button("Release Limpo", id="build_clean_release", classes="menu-btn")
        yield Button("Release Otimizado", id="build_opt_release", classes="menu-btn")
        yield Button("Kernel", id="build_kernel", classes="menu-btn")
        yield Button("Bootloader", id="build_bootloader", classes="menu-btn")
        yield Button("Serviços", id="build_services", classes="menu-btn")
        yield Button("Apps", id="build_apps", classes="menu-btn")
        yield Button("Gerar VDI", id="create_vdi", classes="menu-btn")
        yield Button("QEMU", id="run_qemu", classes="menu-btn")
        yield Button("Monitor Serial", id="listen_serial", classes="menu-btn")
        yield Button("Analisar Log", id="analyze_log", classes="menu-btn")
        yield Button("Inspecionar SSE", id="inspect_kernel", classes="menu-btn")
        yield Button("Estatísticas", id="statistics", classes="menu-btn")
        yield Button("Limpar Build", id="clean", classes="menu-btn")
        yield Button("Ambiente", id="environment", classes="menu-btn")
        yield Button("Tela Cheia", id="toggle_menu", classes="menu-btn")
        yield Button("Copiar Log", id="copy_log", classes="menu-btn")
        yield Button("Sair", id="quit", classes="menu-btn-quit")


class LogPanel(Static):
    """Log display panel with copy support."""
    
    # Track if this panel has focus
    is_focused: bool = False
    
    # Internal log storage (plain text)
    _log_lines: list[str] = []

    def compose(self) -> ComposeResult:
        self.log_widget = RichLog(highlight=True, markup=True, auto_scroll=True, max_lines=10000)
        self.log_widget.can_focus = True
        self._log_lines = []
        yield self.log_widget
    
    def on_focus(self, event) -> None:
        """Track when panel gains focus."""
        self.is_focused = True
        self.add_class("focused")
    
    def on_blur(self, event) -> None:
        """Track when panel loses focus."""
        self.is_focused = False
        self.remove_class("focused")
    
    def on_key(self, event: Key) -> None:
        """Handle key events - Ctrl+C copies log when focused."""
        if event.key == "ctrl+c" and self.is_focused:
            self.copy_to_clipboard()
            event.prevent_default()
            event.stop()
    
    def copy_to_clipboard(self) -> None:
        """Copy all log content to clipboard."""
        try:
            import pyperclip
            
            # Get plain text content
            text = self.get_plain_text()
            
            if text:
                pyperclip.copy(text)
                # Show feedback
                self.app.notify("📋 Log copiado para área de transferência!", severity="information")
            else:
                self.app.notify("⚠ Log vazio", severity="warning")
                
        except ImportError:
            # pyperclip not available, try alternative
            try:
                import subprocess
                text = self.get_plain_text()
                # Windows clip command
                process = subprocess.Popen(['clip'], stdin=subprocess.PIPE)
                process.communicate(text.encode('utf-8'))
                self.app.notify("📋 Log copiado!", severity="information")
            except Exception as e:
                self.app.notify(f"❌ Erro ao copiar: {e}", severity="error")
        except Exception as e:
            self.app.notify(f"❌ Erro ao copiar: {e}", severity="error")
    
    def get_plain_text(self) -> str:
        """Get log content as plain text (strips Rich markup)."""
        # Join stored plain text lines
        return "\n".join(self._log_lines)
    
    def _strip_markup(self, text: str) -> str:
        """Remove Rich markup tags from text."""
        # Remove [tag] and [/tag] patterns
        return re.sub(r'\[/?[^\]]+\]', '', text)

    def add_log(self, message: str, is_markup: bool = False):
        """Add a log line."""
        if not hasattr(self, 'log_widget') or not self.log_widget:
            return

        ts = datetime.now().strftime("%H:%M:%S")

        if is_markup:
            content = message
            # Store plain text version
            self._log_lines.append(self._strip_markup(message))
        else:
            # Escape Rich markup
            content = message.replace("[", "\\[")
            self._log_lines.append(message)

        self.log_widget.write(content)

    def add_raw(self, line: str):
        """Add raw line (with colorization)."""
        if hasattr(self, 'log_widget') and self.log_widget:
            # Store original line (plain text)
            self._log_lines.append(line)
            
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
        self._log_lines = []
