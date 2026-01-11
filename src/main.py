import asyncio
import sys
import shutil
import time
from pathlib import Path

# Captura de tecla compatível com Linux/Unix
import tty
import termios

# Adiciona o diretório 'src' ao path do python para permitir imports relativos
sys.path.append(str(Path(__file__).parent))

from core.config import load_config
from core.paths import Paths
from core.logger import get_logger, Colors

# Imports dos módulos de construção e execução
from build.dist import DistBuilder
from build.initramfs import InitramfsBuilder
from build.image import ImageBuilder

from runner.monitor import QemuMonitor
from runner.serial import PipeListener, SerialColorizer
from runner.streams import StreamSource

logger = get_logger()

class AnvilCLI:
    """
    Interface de Linha de Comando do Anvil.
    Gerencia as chamadas para os builders e runners.
    """
    
    def __init__(self):
        self.config = load_config()
        self.paths = Paths(self.config.project_root)

    async def run_cargo(self, name: str, path: Path, target: str = None, profile: str = "release") -> bool:
        """Executa 'cargo build' para um componente específico."""
        logger.info(f"Construindo {name}...")
        
        cmd = ["cargo", "build"]
        if profile == "release": cmd.append("--release")
        elif profile != "debug": cmd.extend(["--profile", profile])
        
        if target: cmd.extend(["--target", target])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, cwd=path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            
            # Lê a saída em tempo real
            while True:
                line = await process.stdout.readline()
                if not line: break
                decoded = line.decode("utf-8", errors="replace").rstrip()
                if decoded:
                     # Imprime saída do cargo em cinza para não poluir
                    print(f"{Colors.GREY}  | {decoded}{Colors.RESET}")
            
            await process.wait()
            if process.returncode == 0:
                logger.success(f"{name} pronto!")
                return True
                
            logger.error(f"Erro em {name}!")
            return False
        except Exception as e:
            logger.error(f"Exceção ao rodar cargo: {e}")
            return False

    async def build_release(self):
        """Compila tudo em modo Release."""
        logger.header("Build Total (Release)")
        
        if not await self.run_cargo("Kernel", self.paths.forge, profile="release"): return
        if not await self.run_cargo("Bootloader", self.paths.ignite, target="x86_64-unknown-uefi", profile="release"): return
        
        for svc in self.config.components.services:
            if not await self.run_cargo(svc.name, self.paths.root / svc.path, target=svc.target, profile="release"): return
            
        for app in self.config.components.apps:
            if not await self.run_cargo(app.name, self.paths.root / app.path, target=app.target, profile="release"): return
            
        DistBuilder(self.paths, self.config).prepare(profile="release")
        await InitramfsBuilder(self.paths, self.config).build(profile="release")
        logger.success("Build Release concluída!")

    async def build_clean_release(self):
        """
        Compila Kernel em 'clean-release' (sem tracers) e o resto em 'release'.
        Isso gera um kernel mais limpo para produção.
        """
        logger.header("Build Limpa (Zero Tracer)")
        
        if not await self.run_cargo("Kernel", self.paths.forge, profile="clean-release"): return
        if not await self.run_cargo("Bootloader", self.paths.ignite, target="x86_64-unknown-uefi", profile="release"): return
        
        for svc in self.config.components.services:
            if not await self.run_cargo(svc.name, self.paths.root / svc.path, target=svc.target, profile="release"): return
        
        for app in self.config.components.apps:
            if not await self.run_cargo(app.name, self.paths.root / app.path, target=app.target, profile="release"): return
        
        logger.info("Implantando artefatos limpos...")
        # Copia o kernel clean-release para o lugar do release para ser pego pelo DistBuilder
        try:
            shutil.copy2(self.paths.kernel_binary("clean-release"), self.paths.kernel_binary("release"))
        except Exception as e:
            logger.error(f"Falha ao copiar kernel clean: {e}")
            return

        DistBuilder(self.paths, self.config).prepare(profile="release")
        await InitramfsBuilder(self.paths, self.config).build(profile="release")
        logger.success("Build Limpa concluída!")

    async def build_opt_release(self):
        """Compila tudo em modo Otimizado (opt-release)."""
        logger.header("Build Otimizada")
        
        if not await self.run_cargo("Kernel", self.paths.forge, profile="opt-release"): return
        if not await self.run_cargo("Bootloader", self.paths.ignite, target="x86_64-unknown-uefi", profile="opt-release"): return
        
        for svc in self.config.components.services:
            if not await self.run_cargo(svc.name, self.paths.root / svc.path, target=svc.target, profile="opt-release"): return
            
        for app in self.config.components.apps:
            if not await self.run_cargo(app.name, self.paths.root / app.path, target=app.target, profile="opt-release"): return
            
        DistBuilder(self.paths, self.config).prepare(profile="opt-release")
        await InitramfsBuilder(self.paths, self.config).build(profile="opt-release")
        logger.success("Build Otimizada concluída!")

    # Atalhos para compilar componentes individuais
    async def build_kernel(self): await self.run_cargo("Kernel", self.paths.forge)
    async def build_bootloader(self): await self.run_cargo("Bootloader", self.paths.ignite, target="x86_64-unknown-uefi")
    async def build_services(self):
        for svc in self.config.components.services: await self.run_cargo(svc.name, self.paths.root / svc.path, target=svc.target)
    async def build_apps(self):
        for app in self.config.components.apps: await self.run_cargo(app.name, self.paths.root / app.path, target=app.target)

    async def create_vdi(self):
        """Cria imagem de disco VDI para VirtualBox."""
        logger.header("Criando VDI")
        builder = ImageBuilder(self.paths, self.config, log=logger)
        await builder.build_vdi(profile="release")

    async def run_qemu(self, gdb=False):
        """Inicia QEMU com monitoramento."""
        # Verificação rápida se existe algo bootável
        boot_efi = self.paths.dist_qemu / "EFI" / "BOOT" / "BOOTX64.EFI"
        if not boot_efi.exists():
            logger.warning("Bootloader não encontrado! Você rodou a opção [1] Release?")
            if input("Continuar mesmo assim? (s/N) > ").lower() != "s": return

        logger.header("Inicializando QEMU")
        try:
            # cfg = QemuConfig(...) -> Removido pois config agora é hardcoded no runner
            monitor = QemuMonitor(self.paths, self.config, stop_on_exception=True, show_serial=True)
            
            # Callback para imprimir linhas seriais coloridas foi removido pois show_serial=True já faz isso
            # via logger.raw() que agora tem flush=True
            
            result = await monitor.run_monitored()
            if result.crashed: logger.error(f"CRASH Detectado: {result.crash_info}")
        finally: logger.header("QEMU Finalizado")

    async def listen_serial(self):
        """Modo standalone de escuta serial."""
        logger.info("Aguardando conexão Serial Pipe...")
        
        def on_line(line):
            print(line, end="")
            
        listener = PipeListener(r"\\.\pipe\VBoxCom1", on_line=on_line)
        await listener.start()
        
        logger.info("Monitor Serial Ativo. Pressione Ctrl+C para sair.")
        try:
            while True:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            pass
        finally:
            listener.stop()
            logger.info("Parado.")

    async def statistics(self):
        """Conta linhas de código do projeto."""
        logger.header("Estatísticas")
        logger.info("Analisando código fonte...")
        
        def count_path(path: Path) -> tuple[int, int, int]:
            """Conta arquivos, linhas totais e linhas de código (aprox)."""
            t_files, t_lines, t_code = 0, 0, 0
            if not path.exists(): return 0, 0, 0
            for p in path.rglob("*.rs"):
                if "target" in p.parts: continue
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        t_files += 1
                        lines = f.readlines()
                        t_lines += len(lines)
                        # contagem simplista de código não vazio/comentário
                        t_code += len([l for l in lines if l.strip() and not l.strip().startswith("//")])
                except: pass
            return t_files, t_lines, t_code

        def scan_crates(base_path: Path) -> tuple[int, int, int]:
            """Analisa submódulos/crates em uma pasta."""
            t_f, t_l, t_c = 0, 0, 0
            if not base_path.exists(): return 0, 0, 0
            for item in base_path.iterdir():
                if item.is_dir() and ((item / "Cargo.toml").exists() or (item / "src").exists()):
                    f, l, c = count_path(item)
                    t_f += f; t_l += l; t_c += c
            return t_f, t_l, t_c

        items = [
            ("Kernel", self.paths.forge),
            ("Bootloader", self.paths.ignite),
            ("Compositor", self.paths.root / "firefly" / "compositor"),
            ("Shell", self.paths.root / "firefly" / "shell"),
        ]
        
        groups = [
            ("Services", self.paths.services),
            ("Apps", self.paths.root / "firefly" / "apps"),
            ("Libs", self.paths.lib),
            ("SDK", self.paths.sdk),
        ]

        grand_files = 0
        grand_code = 0

        print(f"\n{Colors.BOLD}{'Componente':<20} | {'Arquivos':<10} | {'Linhas':<15}{Colors.RESET}")
        print("-" * 55)

        for name, path in items:
            f, l, c = count_path(path)
            if f > 0:
                print(f"{name:<20} | {f:<10} | {Colors.GREEN}{c:<15,}{Colors.RESET}")
                grand_files += f; grand_code += c

        for name, path in groups:
            f, l, c = scan_crates(path)
            if f > 0:
                print(f"{name:<20} | {f:<10} | {Colors.GREEN}{c:<15,}{Colors.RESET}")
                grand_files += f; grand_code += c

        print("-" * 55)
        print(f"{Colors.CYAN}{'TOTAL':<20} | {grand_files:<10} | {grand_code:<15,}{Colors.RESET}")
        logger.success("Concluído.")

    async def clean(self):
        """Limpa diretórios de build (target e dist)."""
        for p in [self.paths.forge/"target", self.paths.ignite/"target", self.paths.dist]:
            if p.exists(): 
                try: 
                    shutil.rmtree(p)
                    logger.step(f"Removido {p}")
                except Exception as e:
                    logger.error(f"Não foi possível remover {p}: {e}")
        logger.success("Limpo!")

def getch():
    """Captura uma tecla do terminal (compatível com Linux/Unix)."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def clear_screen():
    """Limpa a tela do terminal."""
    import os
    os.system('cls' if os.name == 'nt' else 'clear')

async def main():
    """Loop principal do menu."""
    cli = AnvilCLI()
    
    while True:
        clear_screen()
        print(f"{Colors.BOLD}{Colors.YELLOW}Anvil - RedstoneOS Builder{Colors.RESET}\n")
        
        options = [
            ("1", "Release"),
            ("2", "Release Limpo"),
            ("3", "Release Otimizado"),
            ("4", "Kernel"),
            ("5", "Bootloader"),
            ("6", "Serviços"),
            ("7", "Apps"),
            ("8", "Gerar VDI"),
            ("9", "QEMU"),
            ("0", "Monitor Serial"),
            ("s", "Estatísticas"),
            ("c", "Limpar Build"),
            ("q", "Sair"),
        ]
        
        for key, name in options:
            print(f" {Colors.CYAN}[{key}]{Colors.RESET} {name}")
            
        print()
        print(f"{Colors.BOLD}Opção > {Colors.RESET}", end="", flush=True)
        choice = getch().lower()
        print(choice) # Ecoa a tecla pressionada

        if choice == "q": break
        
        print()
        try:
            if choice == "1": await cli.build_release()
            elif choice == "2": await cli.build_clean_release()
            elif choice == "3": await cli.build_opt_release()
            elif choice == "4": await cli.build_kernel()
            elif choice == "5": await cli.build_bootloader()
            elif choice == "6": await cli.build_services()
            elif choice == "7": await cli.build_apps()
            elif choice == "8": await cli.create_vdi()
            elif choice == "9": await cli.run_qemu()
            elif choice == "0": await cli.listen_serial()
            elif choice == "s": await cli.statistics()
            elif choice == "c": await cli.clean()
        except KeyboardInterrupt:
            logger.warning("Interrompido!")
        except Exception as e:
            logger.error(f"Exceção Inesperada: {e}")
        
        print(f"\n{Colors.GREY}Pressione qualquer tecla para continuar...{Colors.RESET}")
        getch()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
