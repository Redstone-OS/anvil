# Anvil - Build System do Redstone OS
# Menu interativo para Windows PowerShell

$ErrorActionPreference = "Stop"
$script:ProjectRoot = Split-Path -Parent $PSScriptRoot
$script:AnvilPath = Join-Path $script:ProjectRoot "anvil\target\release\anvil.exe"

# --- Funções Utilitárias ---

function Write-Header {
    param([string]$Title)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "   $Title" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Ensure-Targets {
    Write-Host "🔍 Verificando targets Rust..." -ForegroundColor Yellow
    
    $targets = @("x86_64-unknown-none", "x86_64-unknown-uefi")
    
    foreach ($target in $targets) {
        $installed = rustup target list --installed | Select-String -Pattern $target -Quiet
        
        if (-not $installed) {
            Write-Host "  📥 Instalando target $target..." -ForegroundColor Yellow
            rustup target add $target
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ✓ Target $target instalado" -ForegroundColor Green
            } else {
                Write-Host "  ✗ Falha ao instalar $target" -ForegroundColor Red
                return $false
            }
        } else {
            Write-Host "  ✓ Target $target já instalado" -ForegroundColor Green
        }
    }
    
    return $true
}

function Build-Component {
    param(
        [string]$Name,
        [string]$Path,
        [string]$Target,
        [string]$Profile = "debug"
    )
    
    Write-Host "🔨 Compilando $Name..." -ForegroundColor Yellow
    Push-Location (Join-Path $script:ProjectRoot $Path)
    
    try {
        if ($Profile -eq "release") {
            cargo build --release --target $Target
        } else {
            cargo build --target $Target
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ $Name OK" -ForegroundColor Green
            return $true
        } else {
            Write-Host "  ✗ $Name falhou" -ForegroundColor Red
            return $false
        }
    }
    finally {
        Pop-Location
    }
}

function Build-All {
    param([string]$Profile = "debug")
    
    Write-Header "Build All ($Profile)"
    
    # Verificar e instalar targets necessários
    if (-not (Ensure-Targets)) {
        Write-Host "`n✗ Falha ao configurar targets Rust" -ForegroundColor Red
        return $false
    }
    
    # 1. LibC (dependência)
    if (-not (Build-Component "LibC" "libs\libc" "x86_64-unknown-none" $Profile)) {
        return $false
    }
    
    # 2. Kernel
    if (-not (Build-Component "Kernel" "forge" "x86_64-unknown-none" $Profile)) {
        return $false
    }
    
    # 3. Bootloader
    if (-not (Build-Component "Bootloader" "ignite" "x86_64-unknown-uefi" $Profile)) {
        return $false
    }
    
    # 4. Init
    if (-not (Build-Component "Init" "services\init" "x86_64-unknown-none" $Profile)) {
        return $false
    }
    
    Write-Host "`n✓ Todos os componentes compilados com sucesso!" -ForegroundColor Green
    return $true
}

function Copy-ToQemu {
    param([string]$Profile = "debug")
    
    Write-Host "`n📦 Copiando para dist/qemu/..." -ForegroundColor Yellow
    
    $distPath = Join-Path $script:ProjectRoot "dist\qemu"
    
    # Limpar dist/qemu/ completamente
    if (Test-Path $distPath) {
        Remove-Item "$distPath\*" -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    # Criar estrutura UEFI
    New-Item -ItemType Directory -Path "$distPath\EFI\BOOT" -Force | Out-Null
    New-Item -ItemType Directory -Path "$distPath\initfs\bin" -Force | Out-Null
    
    # Copiar bootloader
    $bootloader = Join-Path $script:ProjectRoot "ignite\target\x86_64-unknown-uefi\$Profile\ignite.efi"
    if (Test-Path $bootloader) {
        Copy-Item $bootloader "$distPath\EFI\BOOT\BOOTX64.EFI" -Force
        Write-Host "  ✓ Bootloader copiado" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Bootloader não encontrado: $bootloader" -ForegroundColor Red
        return $false
    }
    
    # Copiar kernel
    $kernel = Join-Path $script:ProjectRoot "forge\target\x86_64-unknown-none\$Profile\forge"
    if (Test-Path $kernel) {
        Copy-Item $kernel "$distPath\forge" -Force
        Write-Host "  ✓ Kernel copiado" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Kernel não encontrado: $kernel" -ForegroundColor Red
        return $false
    }
    
    # Copiar init
    $init = Join-Path $script:ProjectRoot "services\init\target\x86_64-unknown-none\$Profile\init"
    if (Test-Path $init) {
        Copy-Item $init "$distPath\initfs\bin\init" -Force
        Write-Host "  ✓ Init copiado" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Init não encontrado: $init" -ForegroundColor Red
        return $false
    }
    
    Write-Host "`n✓ Dist/qemu atualizado!" -ForegroundColor Green
    Write-Host "  Localização: $distPath" -ForegroundColor Cyan
    return $true
}


# --- Menu Loop ---

while ($true) {
    Clear-Host
    Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                                        ║" -ForegroundColor Cyan
    Write-Host "║      🔨 Anvil - Redstone OS 🔨        ║" -ForegroundColor Cyan
    Write-Host "║   A bigorna onde forjamos o sistema   ║" -ForegroundColor Cyan
    Write-Host "║                                        ║" -ForegroundColor Cyan
    Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "┌─ Build & Run ─────────────────────────┐" -ForegroundColor Yellow
    Write-Host "│ [1] Build (Debug)                     │"
    Write-Host "│ [2] Build (Release)                   │"
    Write-Host "│ [3] Build Kernel                      │"
    Write-Host "│ [4] Build Bootloader                  │"
    Write-Host "│ [5] Build Userspace                   │"
    Write-Host "│ [6] Run (QEMU)                        │"
    Write-Host "│ [7] Run com GDB                       │"
    Write-Host "└───────────────────────────────────────┘"
    # Write-Host ""
    # Write-Host "┌─ Distribution ────────────────────────┐" -ForegroundColor Yellow
    # Write-Host "│ [8] Criar Distribuição                │"
    # Write-Host "│ [9] Criar ISO                         │"
    # Write-Host "│ [10] Gravar em USB                    │"
    # Write-Host "└───────────────────────────────────────┘"
    # Write-Host ""
    # Write-Host "┌─ Recipes ─────────────────────────────┐" -ForegroundColor Yellow
    # Write-Host "│ [11] Listar Receitas                  │"
    # Write-Host "│ [12] Usar Receita Minimal             │"
    # Write-Host "│ [13] Usar Receita Desktop             │"
    # Write-Host "│ [14] Usar Receita Server              │"
    # Write-Host "└───────────────────────────────────────┘"
    # Write-Host ""
    # Write-Host "┌─ Templates ───────────────────────────┐" -ForegroundColor Yellow
    # Write-Host "│ [15] Listar Templates                 │"
    # Write-Host "│ [16] Criar Novo Driver                │"
    # Write-Host "│ [17] Criar Novo Service               │"
    # Write-Host "└───────────────────────────────────────┘"
    # Write-Host ""
    # Write-Host "┌─ Quality ─────────────────────────────┐" -ForegroundColor Yellow
    # Write-Host "│ [18] Check (Verificar código)         │"
    # Write-Host "│ [19] Format (Formatar código)         │"
    # Write-Host "│ [20] Clippy (Linter)                  │"
    # Write-Host "│ [21] Doc (Gerar documentação)         │"
    # Write-Host "└───────────────────────────────────────┘"
    Write-Host ""
    Write-Host "┌─ Utilities ───────────────────────────┐" -ForegroundColor Yellow
    Write-Host "│ [22] Clean (Limpar artefatos)         │"
    Write-Host "│ [23] Env (Mostrar ambiente)           │"
    Write-Host "│ [Q] Sair                              │"
    Write-Host "└───────────────────────────────────────┘"
    Write-Host ""
    
    $choice = Read-Host "Selecione uma opção"
    
    try {
        switch ($choice) {
            # Build & Run
            "1" { 
                Write-Header "Build para QEMU (Debug)"
                
                if (Build-All "debug") {
                    if (Copy-ToQemu "debug") {
                        Write-Host "`n🎉 Build completo! Pronto para testar no QEMU" -ForegroundColor Green
                    }
                }
                
                Pause 
            }
            "2" { 
                Write-Header "Build Release"
                Run-Anvil @("build", "--release")
                if ($LASTEXITCODE -eq 0) {
                    Copy-ToDist "release"
                }
                Pause 
            }
            "3" { 
                Write-Header "Build Kernel"
                Run-Anvil @("build", "kernel", "--release")
                if ($LASTEXITCODE -eq 0) {
                    Copy-ToDist "release"
                }
                Pause 
            }
            "4" { 
                Write-Header "Build Bootloader"
                Run-Anvil @("build", "bootloader", "--release")
                if ($LASTEXITCODE -eq 0) {
                    Copy-ToDist "release"
                }
                Pause 
            }
            "5" { 
                Write-Header "Build Userspace"
                Run-Anvil @("build", "userspace", "--release")
                if ($LASTEXITCODE -eq 0) {
                    Copy-ToDist "release"
                }
                Pause 
            }
            "6" { 
                Write-Header "Run QEMU"
                Run-Anvil @("run")
                Pause 
            }
            "7" { 
                Write-Header "Run com GDB"
                Run-Anvil @("run", "--gdb")
                Pause 
            }
            
            # Distribution
            "8" { 
                Write-Header "Criar Distribuição"
                Run-Anvil @("dist", "--release")
                Pause 
            }
            "9" { 
                Write-Header "Criar ISO"
                Run-Anvil @("iso")
                Pause 
            }
            "10" { 
                Write-Header "Gravar em USB"
                Run-Anvil @("usb")
                Pause 
            }
            
            # Recipes
            "11" { 
                Write-Header "Receitas Disponíveis"
                Run-Anvil @("recipe", "list")
                Pause 
            }
            "12" { 
                Write-Header "Usando Receita Minimal"
                Run-Anvil @("recipe", "use", "minimal")
                Pause 
            }
            "13" { 
                Write-Header "Usando Receita Desktop"
                Run-Anvil @("recipe", "use", "desktop")
                Pause 
            }
            "14" { 
                Write-Header "Usando Receita Server"
                Run-Anvil @("recipe", "use", "server")
                Pause 
            }
            
            # Templates
            "15" { 
                Write-Header "Templates Disponíveis"
                Run-Anvil @("template", "list")
                Pause 
            }
            "16" { 
                Write-Header "Criar Novo Driver"
                $name = Read-Host "Nome do driver"
                if ($name) {
                    Run-Anvil @("template", "new", "driver", $name)
                }
                Pause 
            }
            "17" { 
                Write-Header "Criar Novo Service"
                $name = Read-Host "Nome do service"
                if ($name) {
                    Run-Anvil @("template", "new", "service", $name)
                }
                Pause 
            }
            
            # Quality
            "18" { 
                Write-Header "Check"
                Run-Anvil @("check")
                Pause 
            }
            "19" { 
                Write-Header "Format"
                Run-Anvil @("fmt")
                Pause 
            }
            "20" { 
                Write-Header "Clippy"
                Run-Anvil @("clippy")
                Pause 
            }
            "21" { 
                Write-Header "Documentação"
                Run-Anvil @("doc", "--open")
                Pause 
            }
            
            # Utilities
            "22" { 
                Write-Header "Clean"
                $all = Read-Host "Limpar tudo incluindo cache? (S/N)"
                if ($all -eq 'S' -or $all -eq 's') {
                    Run-Anvil @("clean", "--all")
                } else {
                    Run-Anvil @("clean")
                }
                Pause 
            }
            "23" { 
                Write-Header "Ambiente"
                Run-Anvil @("env")
                Pause 
            }
            
            # Sair
            "Q" { exit }
            "q" { exit }
            
            Default { 
                Write-Host "❌ Opção inválida" -ForegroundColor Red
                Start-Sleep -Seconds 1
            }
        }
    }
    catch {
        Write-Host "❌ Erro durante execução: $_" -ForegroundColor Red
        Pause
    }
}
