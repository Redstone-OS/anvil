# Anvil - Comandos

Documentação completa de todos os comandos do Anvil.

## Build & Run

### anvil build

Compila o sistema.

```bash
anvil build                    # Debug
anvil build --release          # Release
anvil build kernel             # Apenas kernel
anvil build bootloader         # Apenas bootloader
anvil build drivers            # Apenas drivers
anvil build userspace          # Apenas userspace
```

### anvil run

Executa no QEMU.

```bash
anvil run                      # Debug
anvil run --release            # Release
anvil run --gdb                # Com GDB server
anvil run --kvm                # Com KVM
```

## Distribution

### anvil dist

Cria distribuição.

```bash
anvil dist                     # Dist completa
anvil dist --minimal           # Dist mínima
anvil dist --recipe desktop    # Usando receita
```

### anvil iso

Cria ISO bootável.

```bash
anvil iso                      # ISO padrão
anvil iso --recipe server      # ISO servidor
```

### anvil usb

Grava em USB.

```bash
anvil usb                      # Interativo
anvil usb --device /dev/sdb    # Direto
```

## Recipes

### anvil recipe list

Lista receitas disponíveis.

### anvil recipe show <nome>

Mostra detalhes de uma receita.

### anvil recipe use <nome>

Usa uma receita.

## Templates

### anvil template list

Lista templates disponíveis.

### anvil template new <tipo> <nome>

Cria novo componente a partir de template.

```bash
anvil template new driver mydriver
anvil template new service myservice
anvil template new app myapp
```

## Quality

### anvil check

Verifica código (cargo check).

### anvil fmt

Formata código (cargo fmt).

### anvil clippy

Linter (cargo clippy).

### anvil doc

Gera documentação.

```bash
anvil doc              # Gera docs
anvil doc --open       # Abre no browser
```

## Utilities

### anvil clean

Limpa artefatos.

```bash
anvil clean            # Limpa build
anvil clean --all      # Limpa tudo
```

### anvil env

Mostra ambiente de desenvolvimento.

---

TODO(prioridade=média, versão=v1.0): Adicionar mais exemplos e detalhes
