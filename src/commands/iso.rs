//! Comando iso - Cria ISO bootável
//!
//! # TODO(prioridade=média, versão=v1.0)
//! Implementar criação de ISO

use anyhow::Result;
use colored::*;

pub fn run(recipe: Option<String>, _verbose: bool) -> Result<()> {
    println!("{}", "💿 Criando ISO bootável...".bright_yellow());

    if let Some(r) = recipe {
        println!("   Receita: {}", r.bright_green());
    }

    // TODO(prioridade=média, versão=v1.0): Implementar criação de ISO
    println!("{}", "TODO: Implementar criação de ISO".yellow());
    println!("{}", "  - Verificar se dist/ existe".yellow());
    println!("{}", "  - Detectar ferramenta (oscdimg/xorriso)".yellow());
    println!("{}", "  - Criar ISO bootável".yellow());

    Ok(())
}
