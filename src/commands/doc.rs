//! Comando doc - Gera documentação
use anyhow::Result;
use colored::*;

pub fn run(open: bool, _verbose: bool) -> Result<()> {
    println!("{}", "📚 Gerando documentação...".bright_yellow());
    
    if open {
        println!("   Abrindo no browser após gerar");
    }

    // TODO(prioridade=baixa, versão=v1.0): cargo doc em todos os componentes
    println!("{}", "TODO: Implementar cargo doc".yellow());
    Ok(())
}
