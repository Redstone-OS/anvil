//! Comando usb - Grava em USB
//!
//! # TODO(prioridade=média, versão=v1.0)
//! Migrar lógica do build.ps1::Burn-USB()

use anyhow::Result;
use colored::*;

pub fn run(device: Option<String>, _verbose: bool) -> Result<()> {
    println!("{}", "💾 Gravando em USB...".bright_yellow());

    if let Some(d) = device {
        println!("   Dispositivo: {}", d.bright_green());
    } else {
        println!("{}", "   Modo interativo".bright_cyan());
    }

    // TODO(prioridade=média, versão=v1.0): Implementar gravação em USB
    println!("{}", "TODO: Implementar gravação em USB".yellow());
    println!("{}", "  - Listar dispositivos USB".yellow());
    println!("{}", "  - Confirmar com usuário (DESTRUTIVO!)".yellow());
    println!("{}", "  - Formatar como FAT32".yellow());
    println!("{}", "  - Copiar arquivos de dist/".yellow());
    println!("{}", "  - Verificar se solicitado".yellow());

    Ok(())
}
