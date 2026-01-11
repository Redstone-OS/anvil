#!/bin/bash
# Verifica dependências necessárias para rodar o Anvil no Debian

echo "Verificando dependências do Anvil..."
echo ""

MISSING=""

# Verifica QEMU
if ! command -v qemu-system-x86_64 &> /dev/null; then
    echo "❌ qemu-system-x86_64 não encontrado"
    MISSING="$MISSING qemu-system-x86"
else
    echo "✓ qemu-system-x86_64 encontrado"
fi

# Verifica OVMF (UEFI firmware)
if [ ! -f /usr/share/OVMF/OVMF_CODE.fd ] && [ ! -f /usr/share/qemu/OVMF.fd ]; then
    echo "❌ OVMF não encontrado"
    MISSING="$MISSING ovmf"
else
    echo "✓ OVMF encontrado"
fi

# Verifica Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 não encontrado"
    MISSING="$MISSING python3"
else
    echo "✓ Python 3 encontrado"
fi

# Verifica Rust/Cargo
if ! command -v cargo &> /dev/null; then
    echo "⚠️  Cargo não encontrado (necessário para build)"
    echo "   Instale via: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
else
    echo "✓ Cargo encontrado"
fi

echo ""

if [ -n "$MISSING" ]; then
    echo "Para instalar as dependências faltantes, execute:"
    echo "sudo apt install$MISSING"
    exit 1
else
    echo "✓ Todas as dependências estão instaladas!"
    exit 0
fi
