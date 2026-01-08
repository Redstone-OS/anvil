"""Anvil Runner - QEMU Launcher.

Responsável por montar o comando e executar o QEMU via WSL,
seguindo EXATAMENTE os padrões definidos pelo usuário (hardcoded).
"""

import asyncio
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
        
    def build_command(self) -> str:
        """
        Constrói a linha de comando do QEMU para execução no WSL.
        Hardcoded para garantir fidelidade total ao pedido do usuário.
        """

        
        # Lista HARDCODED sem lógica extra
        cmd_parts = [
            "qemu-system-x86_64",
            "-enable-kvm",
            "-cpu host",
            "-m 2048M",
            "-smp cpus=4,sockets=1,cores=2,threads=2",
            '-drive "file=fat:rw:/mnt/d/Github/RedstoneOS/dist/qemu,format=raw"',
            "-bios /usr/share/qemu/OVMF.fd",
            "-chardev stdio,id=char0,mux=on,logfile=/mnt/d/Github/RedstoneOS/dist/serial.log",
            "-serial chardev:char0",
            "-vga std",
            "-s"
        ]

        
        return " ".join(cmd_parts)
        
    async def start(self):
        """Inicia o processo QEMU."""
        self.log.info("Inicializando QEMU via WSL...")
        
        # Cria o startup.nsh no drive FAT para auto-boot
        # Isso impede que o UEFI pare no Shell
        try:
            startup_nsh = self.paths.dist_qemu / "startup.nsh"
            startup_nsh.write_text(r"fs0:\EFI\BOOT\BOOTX64.EFI")
        except Exception as e:
            self.log.warning(f"Não foi possível criar startup.nsh: {e}")

        env_vars = "export LANG=en_US.UTF-8 &&"
        cmd = self.build_command()
        self.log.debug(f"Comando: {cmd}")
        
        
        self.process = await asyncio.create_subprocess_exec(
            "wsl", "bash", "-c", f"{env_vars} cd /tmp && {cmd}",
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.STDOUT
        )
        self.log.success(f"QEMU rodando (PID: {self.process.pid})")
        return self.process
        
    async def stop(self):
        """Para o QEMU."""
        if self.process:
            self.log.info("Parando QEMU...")
            self.process.terminate()
            try: await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except: self.process.kill()
            self.process = None
