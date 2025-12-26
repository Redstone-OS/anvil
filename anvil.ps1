# Anvil - Build System do Redstone OS
# Menu interativo para Windows PowerShell

$ErrorActionPreference = "Stop"
$script:ProjectRoot = Split-Path -Parent $PSScriptRoot

# --- Configuração ---

# Serviços a compilar (ordem de dependência)
# NOTA: Apenas init por enquanto para simplificar debugging
# Outros serviços serão adicionados após SYS_SPAWN estar implementado
$script:Services = @(
    @{ Name = "init"; Path = "services\init" }
    # @{ Name = "console"; Path = "services\console" }
    # @{ Name = "devices"; Path = "services\devices" }
    # @{ Name = "vfs"; Path = "services\vfs" }
    # @{ Name = "logger"; Path = "services\logger" }
)

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
        [string]$Profile = "release"
    )
    
    Write-Host "🔨 Compilando $Name..." -ForegroundColor Yellow
    Push-Location (Join-Path $script:ProjectRoot $Path)
    
    try {
        # Kernel usa .cargo/config.toml com target customizado
        if ($Name -eq "Kernel") {
            if ($Profile -eq "release") {
                cargo build --release
            } else {
                cargo build
            }
        } else {
            if ($Profile -eq "release") {
                cargo build --release --target $Target
            } else {
                cargo build --target $Target
            }
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

function Build-Services {
    param([string]$Profile = "release")
    
    Write-Host "`n📦 Compilando Serviços..." -ForegroundColor Yellow
    
    foreach ($service in $script:Services) {
        if (-not (Build-Component $service.Name $service.Path "x86_64-unknown-none" $Profile)) {
            return $false
        }
    }
    
    return $true
}

function Build-All {
    param([string]$Profile = "debug")
    
    Write-Header "Build All ($Profile)"
    
    # Verificar targets
    if (-not (Ensure-Targets)) {
        Write-Host "`n✗ Falha ao configurar targets Rust" -ForegroundColor Red
        return $false
    }
    
    # 1. Kernel
    if (-not (Build-Component "Kernel" "forge" "x86_64-unknown-none" $Profile)) {
        return $false
    }
    
    # 2. Bootloader
    if (-not (Build-Component "Bootloader" "ignite" "x86_64-unknown-uefi" $Profile)) {
        return $false
    }
    
    # 3. Serviços
    if (-not (Build-Services $Profile)) {
        return $false
    }
    
    Write-Host "`n✓ Todos os componentes compilados!" -ForegroundColor Green
    return $true
}

function Create-ServicesManifest {
    param([string]$Path)
    
    $manifest = @"
# Manifesto de Serviços - Redstone OS
# /system/manifests/services.toml

[init]
path = "/system/core/init"
restart = "never"
depends = []

# [console]
# path = "/system/services/console"
# restart = "always"
# depends = []

# [devices]
# path = "/system/services/devices"
# restart = "always"
# depends = ["console"]

# [vfs]
# path = "/system/services/vfs"
# restart = "on-failure"
# depends = ["devices"]

# [logger]
# path = "/system/services/logger"
# restart = "always"
# depends = []
"@
    
    $manifest | Out-File -FilePath $Path -Encoding UTF8 -NoNewline
    Write-Host "  ✓ services.toml criado" -ForegroundColor Green
}

function Copy-ToQemu {
    param([string]$Profile = "release")
    
    Write-Host "`n📦 Preparando dist/qemu/..." -ForegroundColor Yellow
    
    $distPath = Join-Path $script:ProjectRoot "dist\qemu"
    
    # Limpar
    if (Test-Path $distPath) {
        Remove-Item "$distPath\*" -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    # Estrutura UEFI
    New-Item -ItemType Directory -Path "$distPath\EFI\BOOT" -Force | Out-Null
    New-Item -ItemType Directory -Path "$distPath\boot" -Force | Out-Null
    
    # Bootloader
    $bootloader = Join-Path $script:ProjectRoot "ignite\target\x86_64-unknown-uefi\$Profile\ignite.efi"
    if (Test-Path $bootloader) {
        Copy-Item $bootloader "$distPath\EFI\BOOT\BOOTX64.EFI" -Force
        Write-Host "  ✓ Bootloader → EFI/BOOT/BOOTX64.EFI" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Bootloader não encontrado" -ForegroundColor Red
        return $false
    }

    # UEFI Shell (opcional)
    $shellSource = Join-Path $script:ProjectRoot "anvil\assets\shellx64.efi"
    if (Test-Path $shellSource) {
        Copy-Item $shellSource "$distPath\EFI\BOOT\shellx64.efi" -Force
        Write-Host "  ✓ UEFI Shell copiado" -ForegroundColor Green
    }

    # Config do bootloader
    $configSource = Join-Path $script:ProjectRoot "anvil\assets\ignite.cfg"
    if (Test-Path $configSource) {
        Copy-Item $configSource "$distPath\ignite.cfg" -Force
        Write-Host "  ✓ ignite.cfg copiado" -ForegroundColor Green
    }
    
    # Kernel
    $kernel = Join-Path $script:ProjectRoot "forge\target\x86_64-redstone\$Profile\forge"
    if (Test-Path $kernel) {
        Copy-Item $kernel "$distPath\boot\kernel" -Force
        Write-Host "  ✓ Kernel → boot/kernel" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Kernel não encontrado" -ForegroundColor Red
        return $false
    }
    
    # InitRAMFS
    Write-Host "`n📦 Criando InitRAMFS..." -ForegroundColor Yellow
    
    $initramfsPath = Join-Path $script:ProjectRoot "anvil\assets\initramfs"
    
    # Limpar e recriar estrutura
    if (Test-Path $initramfsPath) {
        Remove-Item "$initramfsPath\*" -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    # Estrutura Redstone OS
    New-Item -ItemType Directory -Path "$initramfsPath\system\core" -Force | Out-Null
    New-Item -ItemType Directory -Path "$initramfsPath\system\services" -Force | Out-Null
    New-Item -ItemType Directory -Path "$initramfsPath\system\drivers" -Force | Out-Null
    New-Item -ItemType Directory -Path "$initramfsPath\system\manifests" -Force | Out-Null
    New-Item -ItemType Directory -Path "$initramfsPath\runtime\ipc" -Force | Out-Null
    New-Item -ItemType Directory -Path "$initramfsPath\runtime\logs" -Force | Out-Null
    New-Item -ItemType Directory -Path "$initramfsPath\state\system" -Force | Out-Null
    New-Item -ItemType Directory -Path "$initramfsPath\state\services" -Force | Out-Null
    
    Write-Host "  ✓ Estrutura: /system, /runtime, /state" -ForegroundColor Green
    
    # Copiar init
    $init = Join-Path $script:ProjectRoot "services\init\target\x86_64-unknown-none\$Profile\init"
    if (Test-Path $init) {
        Copy-Item $init "$initramfsPath\system\core\init" -Force
        Write-Host "  ✓ /system/core/init" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Init não encontrado" -ForegroundColor Red
        return $false
    }
    
    # Copiar outros serviços (quando existirem)
    foreach ($service in $script:Services) {
        if ($service.Name -eq "init") { continue }
        
        $serviceBin = Join-Path $script:ProjectRoot "$($service.Path)\target\x86_64-unknown-none\$Profile\$($service.Name)"
        if (Test-Path $serviceBin) {
            Copy-Item $serviceBin "$initramfsPath\system\services\$($service.Name)" -Force
            Write-Host "  ✓ /system/services/$($service.Name)" -ForegroundColor Green
        }
    }
    
    # Criar manifesto de serviços
    Create-ServicesManifest "$initramfsPath\system\manifests\services.toml"
    
    # Criar TAR via WSL
    Write-Host "  📦 Criando initfs (tar)..." -ForegroundColor Yellow
    
    $wslInitramfsPath = "/mnt/" + $initramfsPath.Replace(":\", "/").Replace("\", "/").ToLower()
    $wslDistPath = "/mnt/" + $distPath.Replace(":\", "/").Replace("\", "/").ToLower()
    
    wsl tar -cf "$wslDistPath/boot/initfs" -C "$wslInitramfsPath" . 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        $tarSize = (Get-Item "$distPath\boot\initfs").Length
        Write-Host "  ✓ initfs criado ($([math]::Round($tarSize/1024, 2)) KB)" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Falha ao criar TAR (WSL necessário)" -ForegroundColor Red
        return $false
    }
    
    Write-Host "`n✓ dist/qemu pronto!" -ForegroundColor Green
    Write-Host "  Local: $distPath" -ForegroundColor Cyan
    return $true
}

function Run-Qemu {
    Write-Header "Executando QEMU"
    
    $distPath = Join-Path $script:ProjectRoot "dist\qemu"
    $ovaPath = Join-Path $script:ProjectRoot "anvil\assets\OVMF.fd"
    
    if (-not (Test-Path "$distPath\EFI\BOOT\BOOTX64.EFI")) {
        Write-Host "❌ Dist não encontrada. Execute Build primeiro." -ForegroundColor Red
        return
    }
    
    # Verificar OVMF
    if (-not (Test-Path $ovaPath)) {
        Write-Host "❌ OVMF.fd não encontrado em anvil/assets/" -ForegroundColor Red
        Write-Host "   Baixe de: https://github.com/tianocore/edk2/releases" -ForegroundColor Yellow
        return
    }
    
    Write-Host "🚀 Iniciando QEMU..." -ForegroundColor Green
    
    $qemuArgs = @(
        "-bios", $ovaPath,
        "-drive", "format=raw,file=fat:rw:$distPath",
        "-m", "512M",
        "-serial", "stdio",
        "-no-reboot",
        "-no-shutdown"
    )
    
    & qemu-system-x86_64 @qemuArgs
}

function Run-QemuGdb {
    Write-Header "Executando QEMU com GDB"
    
    $distPath = Join-Path $script:ProjectRoot "dist\qemu"
    $ovaPath = Join-Path $script:ProjectRoot "anvil\assets\OVMF.fd"
    
    Write-Host "🔧 QEMU aguardando GDB em localhost:1234" -ForegroundColor Yellow
    Write-Host "   Para conectar: gdb -ex 'target remote :1234'" -ForegroundColor Cyan
    
    $qemuArgs = @(
        "-bios", $ovaPath,
        "-drive", "format=raw,file=fat:rw:$distPath",
        "-m", "512M",
        "-serial", "stdio",
        "-no-reboot",
        "-no-shutdown",
        "-s", "-S"
    )
    
    & qemu-system-x86_64 @qemuArgs
}

function Clean-All {
    Write-Header "Limpando Artefatos"
    
    $paths = @(
        "forge\target",
        "ignite\target",
        "services\init\target",
        "services\console\target",
        "services\devices\target",
        "services\vfs\target",
        "services\logger\target",
        "dist\qemu"
    )
    
    foreach ($path in $paths) {
        $fullPath = Join-Path $script:ProjectRoot $path
        if (Test-Path $fullPath) {
            Write-Host "  🗑️ Removendo $path..." -ForegroundColor Yellow
            Remove-Item $fullPath -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    
    Write-Host "`n✓ Limpeza concluída!" -ForegroundColor Green
}

function Show-Environment {
    Write-Header "Ambiente"
    
    Write-Host "`n📂 Diretórios:" -ForegroundColor Yellow
    Write-Host "   Projeto: $script:ProjectRoot"
    Write-Host "   Forge:   $(Join-Path $script:ProjectRoot 'forge')"
    Write-Host "   Ignite:  $(Join-Path $script:ProjectRoot 'ignite')"
    Write-Host "   Serviços: $(Join-Path $script:ProjectRoot 'services')"
    
    Write-Host "`n🔧 Rust:" -ForegroundColor Yellow
    Write-Host "   $(rustc --version)"
    Write-Host "   $(cargo --version)"
    
    Write-Host "`n🎯 Targets instalados:" -ForegroundColor Yellow
    rustup target list --installed | ForEach-Object { Write-Host "   $_" }
    
    Write-Host "`n📦 Serviços configurados:" -ForegroundColor Yellow
    foreach ($service in $script:Services) {
        Write-Host "   - $($service.Name) ($($service.Path))"
    }
}

# --- Menu Loop ---

while ($true) {
    Clear-Host
    Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║      🔨 Anvil - Redstone OS 🔨         ║" -ForegroundColor Cyan
    Write-Host "║   Build System v2.0                    ║" -ForegroundColor Cyan
    Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "┌─ Build ───────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "│ [1] Build All (Debug)                 │"
    Write-Host "│ [2] Build All (Release)               │"
    Write-Host "│ [3] Build Kernel                      │"
    Write-Host "│ [4] Build Bootloader                  │"
    Write-Host "│ [5] Build Serviços                    │"
    Write-Host "└───────────────────────────────────────┘"
    Write-Host ""
    Write-Host "┌─ Run ─────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "│ [6] Run QEMU                          │"
    Write-Host "│ [7] Run QEMU + GDB                    │"
    Write-Host "└───────────────────────────────────────┘"
    Write-Host ""
    Write-Host "┌─ Utilities ───────────────────────────┐" -ForegroundColor Yellow
    Write-Host "│ [8] Clean                             │"
    Write-Host "│ [9] Ambiente                          │"
    Write-Host "│ [Q] Sair                              │"
    Write-Host "└───────────────────────────────────────┘"
    Write-Host ""
    
    $choice = Read-Host "Selecione"
    
    try {
        switch ($choice) {
            "1" { 
                if (Build-All "debug") {
                    Copy-ToQemu "debug"
                }
                Pause 
            }
            "2" { 
                if (Build-All "release") {
                    Copy-ToQemu "release"
                }
                Pause 
            }
            "3" { 
                Build-Component "Kernel" "forge" "x86_64-unknown-none" "debug"
                Pause 
            }
            "4" { 
                Build-Component "Bootloader" "ignite" "x86_64-unknown-uefi" "debug"
                Pause 
            }
            "5" { 
                Build-Services "debug"
                Pause 
            }
            "6" { 
                Run-Qemu
                Pause 
            }
            "7" { 
                Run-QemuGdb
                Pause 
            }
            "8" { 
                Clean-All
                Pause 
            }
            "9" { 
                Show-Environment
                Pause 
            }
            "Q" { exit }
            "q" { exit }
            Default { 
                Write-Host "❌ Opção inválida" -ForegroundColor Red
                Start-Sleep -Seconds 1
            }
        }
    }
    catch {
        Write-Host "❌ Erro: $_" -ForegroundColor Red
        Pause
    }
}