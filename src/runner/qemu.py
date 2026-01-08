"""Anvil Runner - QEMU Launcher.

Responsável por montar o comando e executar o QEMU via WSL,
seguindo EXATAMENTE os padrões definidos pelo usuário (script boot_redstone.sh).
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
        Baseado no script de referência 'boot_redstone.sh'.
        """
        cfg = override_config or self.config.qemu
        dist_path = Paths.to_wsl(self.paths.dist_qemu)
        internal_log = Paths.to_wsl(self.paths.cpu_log)
        
        # O OVMF é essencial para boot UEFI
        # Se o caminho configurado for relativo, resolve a partir da raiz do projeto
        # Se for absoluto (ex: /usr/share/...), mantém como está
        ovmf_path = cfg.ovmf
        if not ovmf_path.startswith("/"):
            ovmf_path = Paths.to_wsl(self.config.project_root / ovmf_path)
            
        # Montagem dos argumentos, ordem baseada no pedido do usuário
        cmd_parts = [
            "qemu-system-x86_64",
            "-enable-kvm",
            "-cpu host",
            "-m 2048M",           # Fixo conforme pedido, ou usar cfg.memory se quiser flexibilidade
            "-smp cpus=4",
            
            # Disco principal: pasta mapeada como disco FAT
            f"-drive file=fat:rw:'{dist_path}',format=raw,if=virtio",
            
            # Firmware UEFI
            f"-bios '{ovmf_path}'",
            
            # Serial stdio para capturarmos via pipe
            "-serial stdio",
            
            "-monitor none",
            "-no-reboot"
        ]
        
        # Flags de debug (-d ...)
        # O usuário usa: -d cpu_reset,int,mmu,guest_errors,unimp
        flags = cfg.debug_flags or ["cpu_reset", "int", "mmu", "guest_errors", "unimp"]
        if flags:
            cmd_parts.append(f"-d {','.join(flags)}")
        
        # Log interno do QEMU (-D ...)
        cmd_parts.append(f"-D '{internal_log}'")
        
        # GDB (opcional, mantido para funcionalidade da ferramenta)
        if cfg.enable_gdb:
            cmd_parts.append(f"-s -S -p {cfg.gdb_port}")
        
        # Argumentos extras (GPU, etc) definidos no TOML
        extra = cfg.extra_args
        # Garante virtio-gpu se não existir, pois o usuário usa 'if=virtio' no drive mas gpu é device separado
        # O script do usuário não mostra gpu explicito, mas RedstoneOS geralmente precisa.
        # Vou manter a lógica segura: se não tiver no extra, adiciona.
        if not any("virtio-gpu" in str(a) for a in extra):
            if "-device" not in extra:
                cmd_parts.append("-device virtio-gpu-pci")
            
        for arg in extra:
            # Evita duplicar se já adicionamos manualmente
            if arg not in cmd_parts and arg != "-no-reboot": 
                cmd_parts.append(arg)
            
        # IMPORTANTE: Redireciona stderr para stdout (2>&1)
        # Não usaremos 'tee' nem 'perl' aqui dentro. 
        # O Python captura o stdout limpo, e salva o log tratado (sem cores) via classe QemuMonitor.
        full_cmd = " ".join(cmd_parts)
        full_cmd += " 2>&1"
        
        return full_cmd
        
    async def start(self, override_config: Optional[QemuConfig] = None):
        """Inicia o processo QEMU."""
        self.log.info("Inicializando QEMU via WSL...")
        
        # Define LANG para evitar problemas de caractere no perl/bash se fosse usado
        # Mas útil para garantir utf-8 no qemu
        env_vars = "export LANG=en_US.UTF-8 &&"
        
        cmd = self.build_command(override_config)
        self.log.debug(f"Comando: {cmd}")
        
        # Limpa logs anteriores
        self.paths.cpu_log.parent.mkdir(parents=True, exist_ok=True)
        self.paths.cpu_log.write_text("")
        self.paths.serial_log.write_text("")
        
        # Executa via WSL bash
        # cd /tmp é mantido por estabilidade de lock
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
