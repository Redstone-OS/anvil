#!/bin/bash
# Anvil - RedstoneOS Builder
# Script de inicialização para Debian/Linux

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Adiciona src ao PYTHONPATH
export PYTHONPATH="$SCRIPT_DIR/src"

# Verifica Python 3
if ! command -v python3 &> /dev/null; then
    echo "Erro: Python 3 não está instalado."
    exit 1
fi

# Verifica se python3-venv está instalado
if ! python3 -m venv --help &> /dev/null; then
    echo "Erro: python3-venv não instalado."
    echo "Instale com: sudo apt install python3.13-venv"
    exit 1
fi

# Cria o virtual environment se não existir
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Criando virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Falha ao criar venv."
        exit 1
    fi
fi

# Ativa o venv
source venv/bin/activate

# Atualiza pip
pip install --upgrade pip

# Instala dependências
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
else
    # Se não houver requirements, instala toml manualmente
    pip install toml
fi

# Roda o Anvil
exec python src/main.py "$@"
