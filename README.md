# Anvil - Ferramenta de Build do RedstoneOS

O **Anvil** é a ferramenta de automação de build e execução para o RedstoneOS. Ele foi projetado para simplificar o fluxo de desenvolvimento, gerenciando compilação, criação de imagens de disco e execução no emulador QEMU.

Esta é a versão **v2 (Refatorada)**, focada em simplicidade, desempenho e remoção de dependências pesadas de UI.

## 🚀 Funcionalidades

- **Menu Interativo CLI**: Interface de texto simples e rápida.
- **Build Modular**: Compila Kernel, Bootloader, Serviços e Apps individualmente ou em conjunto.
- **Perfis de Build**:
  - `Release`: Build padrão otimizada.
  - `Release Limpo`: Remove tracers de debug do Kernel.
  - `Otimizado`: Build de produção agressiva.
- **Geração de Imagem**: Cria imagens `.vdi` (VirtualBox) e `.raw` prontas para boot.
- **Integração WSL**: Executa comandos de sistema (dd, tar, qemu) via WSL 2 para compatibilidade total com ferramentas Linux.
- **Monitoramento**:
  - Execução do QEMU com captura de logs em tempo real.
  - Colorização automática da saída serial.
  - Detecção automática de **Crashes** (Page Faults, GP, etc).

## 📋 Pré-requisitos

- **Windows 10/11** com **WSL 2** instalado e configurado (Ubuntu/Debian recomendado).
- **Python 3.10+**
- **Rust / Cargo** (nightly para o RedstoneOS).
- **QEMU** instalado no ambiente WSL (`qemu-system-x86_64`).
- **Ferramentas de disco**: `mtools`, `dosfstools` no WSL.

## 🛠️ Instalação

1. Instale a dependência Python (apenas `toml` é necessário agora):
   ```cmd
   pip install -r requirements.txt
   ```

## ▶️ Como Usar

Para iniciar o menu interativo:

```cmd
run.bat
```

Ou diretamente via Python:

```cmd
python src/main.py
```

### Opções do Menu

- `[1] Release`: Compila tudo (Kernel + Bootloader + Userspace) e prepara a pasta `dist`.
- `[2] Release Limpo`: Similar ao Release, mas compila o Kernel sem features de debug pesadas.
- `[3] Release Otimizado`: Build com otimizações máximas (LTO, opt-level=3).
- `[8] Gerar VDI`: Pack da pasta `dist` em uma imagem de disco VirtualBox.
- `[9] QEMU`: Inicia o emulador. A saída serial será mostrada no terminal.
- `[0] Monitor Serial`: Conecta-se ao pipe serial (útil se rodar VirtualBox separadamente).

## 📂 Estrutura do Projeto

```
anvil/
├── src/
│   ├── build/        # Scripts de empacotamento (dist, initfs, image)
│   ├── core/         # Configurações, logs e caminhos
│   ├── runner/       # Gerenciamento do QEMU e Serial
│   └── main.py       # Ponto de entrada da CLI
├── requirements.txt  # Dependências (apenas toml)
├── run.bat          # Launcher Windows
└── anvil.toml       # Configuração global (na raiz do repositório)
```

## 🔧 Configuração

O comportamento do Anvil é controlado pelo arquivo `anvil.toml` na raiz do repositório `RedstoneOS`. Nele você pode ajustar:
- Memória do QEMU.
- Caminhos dos componentes.
- Flags de debug do QEMU.
- Configurações do Bootloader.
