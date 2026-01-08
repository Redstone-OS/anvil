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
        Constrói o comando QEMU idêntico ao boot_redstone.sh.
        Fidelidade total ao script do usuário.
        """
        base_dir = "/mnt/d/Github/RedstoneOS/dist"
        qemu_dir = f"{base_dir}/qemu"
        internal_log = f"{base_dir}/qemu-internal.log"
        serial_log = f"{base_dir}/qemu-serial.log"

        cmd_parts = [
            "qemu-system-x86_64",
            "-enable-kvm",
            "-cpu host",
            "-m 2048M",
            "-smp cpus=4",
            f'-drive file=fat:rw:"{qemu_dir}",format=raw,if=virtio',
            "-bios /usr/share/qemu/OVMF.fd",
            "-serial stdio",
            "-monitor none",
            "-no-reboot",
            "-d cpu_reset,int,mmu,guest_errors,unimp",
            f"-D {internal_log}"
        ]

        full_cmd = " ".join(cmd_parts)
        # O Anvil agora usa o mesmo limpador Perl do seu script para o arquivo de log
        full_cmd += f" | tee >(perl -pe 's/\\e\\[?.*?[\\@-~]//g' >{serial_log})"
        
        return full_cmd
        
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
