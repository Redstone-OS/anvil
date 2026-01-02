# Anvil Build System ⚒️

> **A Ferramenta de Forja do RedstoneOS**

Anvil é o sistema de build, orquestração e depuração oficial do RedstoneOS. Ele abstrai a complexidade de gerenciar múltiplos targets (Kernel, Bootloader, Userland), imagens de disco e execução no QEMU em uma interface unificada.

<div align="center">
  <pre>
  ┌──────────────────────────────────────────────────┐
  │  [1] Build All        [2] Run QEMU               │
  │  [3] Clean            [4] Analyze Logs           │
  └──────────────────────────────────────────────────┘
  </pre>
  <i>Interface TUI moderna e intuitiva</i>
</div>

---

## 🚀 Funcionalidades

### 1. Sistema de Build Unificado
Gerencia a compilação cruzada (Cross-Compilation) de todos os componentes do sistema operacional:
- **Forge Kernel** (x86_64-redstone)
- **Ignite Bootloader** (UEFI)
- **Firefly Desktop** & Services (Userspace)

Tudo configurado via `anvil.toml`. O Anvil sabe exatamente quais flags `rustc`, `objcopy` e `ld` usar para cada componente.

### 2. TUI (Terminal User Interface)
Uma interface rica e interativa para desenvolvedores:
- Mostra logs de build em tempo real com coloração.
- Monitora status de sucesso/falha de cada crate.
- Permite rodar comandos comuns com um clique.

### 3. QEMU Wrapper & Debugging
Esqueça as linhas de comando gigantes do QEMU. O Anvil gerencia:
- BIOS/UEFI (OVMF).
- Dispositivos Serial (COM1) para logging do kernel.
- Redirecionamento de logs para análise.

### 4. Crash Analytics (Dr. Anvil) 🩺
O Anvil monitora a saída serial do QEMU em busca de "Exception Dumps".
Se o kernel der crash (Page Fault, #GPF, etc), o Anvil:
1.  Detecta o vetor de interrompção.
2.  Extrai o RIP (Instruction Pointer).
3.  Usa `addr2line` para apontar **exatamente** qual linha de código Rust causou o crash.
4.  Sugere soluções baseadas em padrões conhecidos (ex: "SSE in Kernel").

---

## 🛠️ Como Usar

### Pré-requisitos
- Python 3.10+
- Rust Nightly (`rustup default nightly`)
- QEMU (`qemu-system-x86_64` no PATH)
- Bibliotecas Python: `pip install -r requirements.txt`

### Executando

**Modo Interativo (TUI):**
```bash
.\run.bat
# ou
python src/tui.py
```

**Modo CLI (Automação/CI):**
```bash
python -m src.cli build kernel --release
python -m src.cli run --headless
```

---

## ⚙️ Configuração (`anvil.toml`)

O coração do Anvil. Define onde estão os códigos fontes e como compilá-los.

```toml
[components.kernel]
path = "forge"
target = "x86_64-redstone"

[qemu]
memory = "512M"
ovmf = "assets/OVMF.fd"
```

## 📁 Estrutura do Projeto

```bash
anvil/
├── anvil.toml          # Configuração Global
├── run.bat             # Launcher Windows
├── src/
│   ├── build/          # Wrappers para Cargo/Rustc
│   ├── runner/         # Gerenciamento do QEMU
│   ├── analysis/       # Motor de Crash Analysis
│   ├── tui/            # Interface Gráfica (Textual)
│   └── cli.py          # Entry point de linha de comando
└── assets/             # BIOS (OVMF) e ícones
```
