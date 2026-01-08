"""Anvil Runner - QEMU Launcher.

Responsável por montar o comando e executar o QEMU via WSL,
seguindo EXATAMENTE os padrões definidos pelo usuário (hardcoded).
"""

import asyncio
from typing import Optional
from core.config import Config, QemuConfig
from core.paths import Paths
from core.logger import Logger, get_logger

class QemuRunner:
    """Gerenciador de processo QEMU."""
    
    def __init__(self, paths: Paths, config: Config, log: Optional[Logger] = None):
        self.paths = paths
        self.config = config
        self.log = log or get_logger()
        self.process = None
        
    def build_command(self, override_config: Optional[QemuConfig] = None) -> str:
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
            "-smp cpus=4",
            f"-drive file=fat:rw:'',format=raw,if=virtio",
            f"-bios '{'",
            "-serial stdio",
            "-monitor none",
            "-no-reboot"
        ]

        # Pipeline Tee/Perl para o log serial (mantido pois usuário confirmou que usa isso)
        serial_log = Paths.to_wsl(self.paths.serial_log)
        perl_cleaner = f"perl -pe 's/\\e\\[?.*?[\\@-~]//g' > '{serial_log}'"
        
        full_cmd = " ".join(cmd_parts)
        full_cmd += f" | tee >({perl_cleaner})"
        
        return full_cmd
        
    async def start(self, override_config: Optional[QemuConfig] = None):
        """Inicia o processo QEMU."""
        self.log.info("Inicializando QEMU via WSL...")
        
        env_vars = "export LANG=en_US.UTF-8 &&"
        cmd = self.build_command(override_config)
        self.log.debug(f"Comando: {cmd}")
        
        # Limpa apenas log serial
        self.paths.serial_log.write_text("")
        
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
