# 🔨 Anvil 4.0

**Build, Run and Diagnostic Tool for RedstoneOS**

Ferramenta profissional em Python para compilar, executar e diagnosticar o RedstoneOS.

## ✨ Features

- **Build automatizado** com validação de artefatos (ELF/PE, checksums)
- **Execução via WSL** com monitoramento dual (serial + CPU log)
- **Detecção de exceções em tempo real** (#GP, #PF, #UD, etc.)
- **Diagnóstico inteligente** com disassembly e busca de símbolos
- **Inspeção de binários** para detectar instruções SSE proibidas
- **CLI moderna** com Typer e **TUI interativa** com Rich

## 📦 Instalação

```bash
cd anvil
pip install -e .
```

Para desenvolvimento:

```bash
pip install -e ".[dev]"
```

## 🚀 Uso

### CLI

```bash
# Build e executa com monitoramento
anvil run

# Build apenas
anvil build [--profile release|debug]

# Build componente específico
anvil build --kernel
anvil build --bootloader
anvil build --services

# Analisar log existente
anvil analyze dist/qemu-internal.log

# Inspecionar kernel
anvil inspect --check-sse    # Busca instruções SSE
anvil inspect --sections     # Lista seções
anvil inspect -a 0xffffffff80001000  # Disassembly

# Estatísticas de código
anvil stats

# Limpar artefatos
anvil clean

# Ambiente
anvil env
```

### Menu Interativo (TUI)

```bash
anvil menu
```

![TUI Menu](docs/tui.png)

## 📁 Estrutura

```
anvil/
├── anvil/
│   ├── core/          # Config, logger, paths, exceptions
│   ├── build/         # Cargo wrapper, artifacts, initramfs, dist
│   ├── runner/        # QEMU, WSL, monitor, streams
│   └── analysis/      # Parser, detector, inspector, diagnostics
├── assets/
│   ├── OVMF.fd
│   ├── ignite.cfg
│   └── initramfs/
├── anvil.toml         # Configuração
└── pyproject.toml
```

## ⚙️ Configuração

Arquivo `anvil.toml`:

```toml
[project]
name = "RedstoneOS"
root = ".."

[components.kernel]
path = "forge"
target = "x86_64-redstone"

[components.bootloader]
path = "ignite"
target = "x86_64-unknown-uefi"

[[components.services]]
name = "init"
path = "services/init"

[qemu]
memory = "512M"
extra_args = ["-no-reboot"]

[qemu.logging]
flags = ["cpu_reset", "int", "mmu", "guest_errors"]

[analysis]
context_lines = 100
auto_inspect_binary = true
stop_on_exception = true
```

## 🔍 Diagnóstico Automático

Quando uma exceção é detectada, o Anvil automaticamente:

1. **Identifica** o tipo de exceção (Page Fault, GPF, etc.)
2. **Extrai** contexto (RIP, CR2, registradores)
3. **Localiza** o símbolo/função usando `addr2line`
4. **Desmonta** o código no ponto de falha com `objdump`
5. **Correlaciona** com padrões conhecidos do RedstoneOS
6. **Sugere** causas prováveis e soluções

### Exemplo de Diagnóstico

```
╔════════════════════════════════════════╗
║ 💥 Page Fault (#PF)                    ║
╚════════════════════════════════════════╝

RIP     0xffffffff80012a40
CR2     0x0000000000000000
Símbolo kernel::mm::vmm::init

🔍 Causa Provável:
   NULL pointer dereference

💡 Sugestões:
   1. Verificar Option/Result não tratados
   2. Verificar ponteiros não inicializados
   3. Verificar uso da função 'kernel::mm::vmm::init'

📋 Código no RIP:
   → 0xffffffff80012a40: mov rax, [rdi]
     0xffffffff80012a43: test rax, rax
     0xffffffff80012a46: je 0xffffffff80012a60
```

## 🛠️ Requisitos

### Windows
- Python 3.11+
- WSL 2 com Ubuntu

### WSL
- qemu-system-x86_64
- binutils (objdump, nm, addr2line)
- OVMF.fd

```bash
# No WSL
sudo apt install qemu-system-x86 binutils
sudo apt install ovmf
```

## 📊 Comparação com Anvil Antigo

| Feature | anvil.ps1 | Anvil 4.0 |
|---------|-----------|-----------|
| Build | ✅ Básico | ✅ Com validação |
| Run QEMU | ✅ | ✅ Via WSL |
| Monitoramento | ❌ | ✅ Dual async |
| Detecção de erros | ❌ | ✅ Tempo real |
| Diagnóstico | ❌ | ✅ Automático |
| Inspeção binário | ❌ | ✅ objdump/nm |
| CLI moderna | ❌ | ✅ Typer |
| TUI | ✅ PowerShell | ✅ Rich |

## 📝 License

MIT - RedstoneOS Team
