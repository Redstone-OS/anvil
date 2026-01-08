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

        # Prepara o OVMF_VARS (copia do template se não existir)
        # O OVMF precisa de CODE (readonly) e VARS (writeable) separados para boot UEFI funcionar
        ovmf_vars_prep = "cp -n /usr/share/OVMF/OVMF_VARS_4M.fd /tmp/OVMF_VARS.fd 2>/dev/null; "
        
        # Lista HARDCODED sem lógica extra
        cmd_parts = [
            ovmf_vars_prep,
            "qemu-system-x86_64",
            "-enable-kvm",
            "-cpu host",
            "-m 2048M",
            "-smp cpus=4",
            "-drive file=fat:rw:/mnt/d/Github/RedstoneOS/dist/qemu,format=raw",
            "-drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
            "-drive if=pflash,format=raw,file=/tmp/OVMF_VARS.fd",
            "-serial stdio",
            "-monitor none",
            "-no-reboot",
            "-device virtio-gpu-pci,xres=1366,yres=768"
        ]

        # Pipeline Tee/Perl para o log serial (mantido pois usuário confirmou que usa isso)
        serial_log = Paths.to_wsl(self.paths.serial_log)
        perl_cleaner = f"perl -pe 's/\\e\\[?.*?[\\@-~]//g' > '{serial_log}'"
        
        full_cmd = " ".join(cmd_parts)
        full_cmd += f" | tee >({perl_cleaner})"
        
        return full_cmd
        
    async def start(self):
        """Inicia o processo QEMU."""
        self.log.info("Inicializando QEMU via WSL...")
        
        env_vars = "export LANG=en_US.UTF-8 &&"
        cmd = self.build_command()
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
