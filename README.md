# Anvil 🔨 - Build System do Redstone OS

**Versão**: 1.0.0  
**Tagline**: "A bigorna onde forjamos o Redstone OS"

---

## 🎯 O que é Anvil?

**Anvil** (Bigorna) é o sistema de build profissional do Redstone OS. Assim como o ferreiro usa a bigorna para forjar ferramentas na forja, o Anvil é onde "forjamos" o Redstone OS.

### Trocadilho Perfeito

- **Ignite** (bootloader) = Acende a forja 🔥
- **Forge** (kernel) = A forja onde tudo é criado ⚒️
- **Anvil** (build tool) = A bigorna onde trabalhamos 🔨
- **Redstone** = A pedra vermelha que alimenta tudo 🔴

---

## 🚀 Instalação

```bash
# Anvil já vem com o Redstone OS
cd D:\Github\Redstone
cargo build -p anvil
```

---

## 📝 Comandos Principais

### Build & Run

```bash
# Build completo
anvil build                    # Debug
anvil build --release          # Release
anvil build --target aarch64   # Cross-compile

# Build específico
anvil build kernel             # Apenas kernel (Forge)
anvil build bootloader         # Apenas bootloader (Ignite)
anvil build drivers            # Apenas drivers
anvil build userspace          # Apenas userspace

# Run no QEMU
anvil run                      # Debug
anvil run --release            # Release
anvil run --gdb                # Com GDB server
anvil run --kvm                # Com KVM
```

### Distribution

```bash
# Criar distribuição
anvil dist                     # Dist completa
anvil dist --minimal           # Dist mínima
anvil dist --desktop           # Dist desktop

# Criar ISO
anvil iso                      # ISO bootável

# Gravar em USB
anvil usb                      # Interativo
anvil usb --device /dev/sdb    # Direto
```

### Recipes (Receitas)

```bash
# Listar receitas
anvil recipe list              # Lista receitas disponíveis
anvil recipe show minimal      # Mostra receita

# Usar receita
anvil recipe use minimal       # Usa receita minimal
anvil recipe use desktop       # Usa receita desktop
```

### Templates

```bash
# Criar a partir de template
anvil template new driver mydriver       # Novo driver
anvil template new service myservice     # Novo serviço
anvil template new app myapp             # Nova aplicação
```

### Quality

```bash
# Verificação
anvil check                    # Cargo check
anvil fmt                      # Formatar código
anvil clippy                   # Linter
anvil doc                      # Gerar documentação
```

### Utilities

```bash
# Utilitários
anvil clean                    # Limpa build
anvil env                      # Mostra ambiente
anvil version                  # Versão
```

---

## 🍳 Sistema de Receitas

Receitas definem **o que** construir e **como** configurar.

### Receitas Disponíveis

1. **minimal** - Sistema mínimo (kernel + init)
2. **desktop** - Desktop completo (GUI + apps)
3. **server** - Servidor (sem GUI)
4. **embedded** - Embarcado
5. **developer** - Desenvolvimento (debug + tools)

### Exemplo de Receita

```toml
# recipes/desktop.toml

[recipe]
name = "desktop"
description = "Redstone OS Desktop Edition"

[components]
kernel = { enabled = true }
bootloader = { enabled = true }
init = { enabled = true }
shell = { enabled = true }
gui = { enabled = true }

[drivers]
essential = ["ps2", "serial", "vga", "ahci"]
optional = ["e1000", "xhci"]

[userspace]
coreutils = ["ls", "cat", "cp", "mv", "rm"]
sysutils = ["ps", "top", "mount"]
```

---

## 📦 Templates

Templates facilitam criação de novos componentes.

```bash
$ anvil template new driver mydriver
🔨 Criando driver 'mydriver'...
✓ Criado drivers/mydriver/
✓ Criado drivers/mydriver/Cargo.toml
✓ Criado drivers/mydriver/src/main.rs
```

---

## 🎨 Configuração

Crie um arquivo `anvil.toml` na raiz do projeto:

```toml
[project]
name = "redstone"
version = "1.0.0"

[targets]
default = "x86_64-unknown-none"

[build]
parallel = true
cache = true

[qemu]
memory = "256M"
serial = "stdio"
```

---

## 📚 Documentação Completa

- [Comandos](docs/COMMANDS.md)
- [Receitas](docs/RECIPES.md)
- [Templates](docs/TEMPLATES.md)
- [Configuração](docs/CONFIG.md)

---

## 🤝 Contribuindo

Anvil é parte do Redstone OS. Contribuições são bem-vindas!

---

## 📄 Licença

MIT License

---

**Anvil** 🔨 - A bigorna onde forjamos o Redstone OS
