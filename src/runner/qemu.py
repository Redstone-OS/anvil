"""Anvil Runner - QEMU Launcher.

Responsável por montar o comando e executar o QEMU nativamente no Linux,
seguindo EXATAMENTE os padrões definidos pelo usuário (hardcoded).
"""

import asyncio
import os
from pathlib import Path
from typing import Optional
from core.config import Config
from core.paths import Paths
from core.logger import Logger, get_logger

class QemuRunner:
    """Gerenciador de processo QEMU."""
    
    def __init__(self, paths: Paths, config: Config, log: Optional[Logger] = None):
        self.paths = paths
        self.config = config
        self.log = log or get_logger()
        self.process = None
        
    def build_command(self) -> list:
        """
        Constrói o comando QEMU para rodar nativamente no Linux.
        Usa os caminhos do projeto atual.
        """
        # Usa os caminhos do projeto (dist/qemu/)
        qemu_dir = str(self.paths.dist_qemu.absolute())
        internal_log = str((self.paths.dist / "qemu-internal.log").absolute())
        serial_log = str((self.paths.dist / "qemu-serial.log").absolute())

        # Detecta o caminho do OVMF
        ovmf_paths = [
            "/usr/share/OVMF/OVMF_CODE_4M.fd",
            "/usr/share/OVMF/OVMF.fd",
            "/usr/share/qemu/OVMF.fd",
            "/usr/share/ovmf/OVMF.fd"
        ]
        ovmf_bios = next((p for p in ovmf_paths if Path(p).exists()), ovmf_paths[0])

        cmd_parts = [
            "qemu-system-x86_64",
            "-enable-kvm",
            "-cpu", "host",
            "-m", "2048M",
            "-smp", "cpus=4",
            "-drive", f"file=fat:rw:{qemu_dir},format=raw,if=virtio",
            "-drive", f"if=pflash,format=raw,readonly=on,file={ovmf_bios}",
            "-serial", "stdio",
            "-display", "gtk",
            "-monitor", "none",
            "-no-reboot",
            "-d", "cpu_reset,int,mmu,guest_errors,unimp",
            "-D", internal_log
        ]

        return cmd_parts
        
    async def start(self):
        """Inicia o processo QEMU."""
        self.log.info("Inicializando QEMU...")

        # Cria o startup.nsh no drive FAT para auto-boot
        # Isso impede que o UEFI pare no Shell
        try:
            startup_nsh = self.paths.dist_qemu / "startup.nsh"
            startup_nsh.write_text(r"fs0:\EFI\BOOT\BOOTX64.EFI")
        except Exception as e:
            self.log.warning(f"Não foi possível criar startup.nsh: {e}")

        cmd = self.build_command()
        self.log.debug(f"Comando: {' '.join(cmd)}")

        # Prepara ambiente - copia o ambiente atual e garante DISPLAY
        env = os.environ.copy()
        env["LANG"] = "en_US.UTF-8"

        # Executa QEMU nativamente no Linux
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.PIPE,
            env=env
        )
        self.log.success(f"QEMU rodando (PID: {self.process.pid})")

        # Inicia tarefa para capturar e salvar serial
        serial_log = str((self.paths.dist / "qemu-serial.log").absolute())
        asyncio.create_task(self._capture_serial(serial_log))

        return self.process

    async def _capture_serial(self, serial_log_path):
        """Captura stdout do QEMU e salva no arquivo serial log."""
        try:
            with open(serial_log_path, 'w', encoding='utf-8') as log_file:
                while self.process and self.process.stdout:
                    line = await self.process.stdout.readline()
                    if not line:
                        break
                    text = line.decode('utf-8', errors='replace')

                    # Escreve no arquivo
                    log_file.write(text)
                    log_file.flush()

                    # Exibe no terminal (sem colorização para não poluir)
                    print(text, end='', flush=True)
        except Exception as e:
            self.log.debug(f"Erro ao capturar serial: {e}")
        
    async def stop(self):
        """Para o QEMU."""
        if self.process:
            self.log.info("Parando QEMU...")
            self.process.terminate()
            try: await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except: self.process.kill()
            self.process = None
