# Anvil - RedstoneOS Builder

Sistema de build e execução para o RedstoneOS, adaptado para rodar nativamente no Debian/Linux.

## Dependências

### Necessárias para Build:
```bash
# Rust e Cargo
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Python 3 e pip
sudo apt install python3 python3-pip python3-venv
```

### Necessárias para execução no QEMU:
```bash
sudo apt install qemu-system-x86 ovmf
```

## Verificação de Dependências

Execute o script de verificação:
```bash
./check_deps.sh
```

## Uso

Execute o Anvil:
```bash
./run.sh
```

O script irá:
1. Criar automaticamente um ambiente virtual Python (venv)
2. Instalar as dependências Python necessárias
3. Executar o menu interativo do Anvil

## Menu do Anvil

- **[1] Release**: Build completo em modo release
- **[2] Release Limpo**: Build sem tracers (produção)
- **[3] Release Otimizado**: Build com otimizações máximas
- **[4] Kernel**: Compila apenas o kernel
- **[5] Bootloader**: Compila apenas o bootloader
- **[6] Serviços**: Compila os serviços
- **[7] Apps**: Compila as aplicações
- **[8] Gerar VDI**: Cria imagem VirtualBox
- **[9] QEMU**: Executa o sistema no QEMU
- **[0] Monitor Serial**: Monitor de saída serial
- **[s] Estatísticas**: Mostra estatísticas do projeto
- **[c] Limpar Build**: Limpa diretórios de build
- **[q] Sair**: Sai do Anvil

## Estrutura

```
anvil/
├── src/
│   ├── main.py          # CLI principal
│   ├── core/            # Núcleo (config, paths, logger)
│   ├── build/           # Builders (dist, initramfs, image)
│   └── runner/          # Executores (QEMU, monitor, serial)
├── run.sh               # Script de inicialização
├── check_deps.sh        # Verificação de dependências
└── requirements.txt     # Dependências Python
```

## Adaptações para Linux

As seguintes mudanças foram feitas para rodar no Debian:

1. **main.py**: Substituído `msvcrt` (Windows) por `termios`/`tty` (Linux)
2. **runner/qemu.py**: Removido WSL, executa QEMU nativamente
3. **run.sh**: Melhorado com venv e instalação automática de dependências
4. **Caminhos OVMF**: Detecta automaticamente o caminho correto do firmware UEFI

## Troubleshooting

### QEMU não inicia
Verifique se KVM está disponível:
```bash
ls /dev/kvm
```

Se não existir, você pode executar sem KVM removendo `-enable-kvm` do comando QEMU em `src/runner/qemu.py`.

### Erro de permissão no /dev/kvm
Adicione seu usuário ao grupo kvm:
```bash
sudo usermod -aG kvm $USER
# Faça logout e login novamente
```
