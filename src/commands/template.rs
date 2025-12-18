//! Comando template - Gerencia templates
//!
//! # TODO(prioridade=média, versão=v1.0)
//! Implementar sistema de templates

use anyhow::Result;
use colored::*;

pub fn list(_verbose: bool) -> Result<()> {
    println!("{}", "📝 Templates disponíveis:".bright_cyan());
    println!();
    println!("  {} - Novo driver", "driver".bright_green());
    println!("  {} - Novo serviço", "service".bright_green());
    println!("  {} - Nova aplicação", "app".bright_green());
    println!("  {} - Nova biblioteca", "lib".bright_green());
    println!();

    Ok(())
}

pub fn new(template_type: &str, name: &str, _verbose: bool) -> Result<()> {
    println!("{}", format!("🔨 Criando {} '{}'...", template_type, name).bright_yellow());

    // TODO(prioridade=média, versão=v1.0): Implementar criação de templates
    println!("{}", "TODO: Implementar criação de templates".yellow());
    println!("{}", "  - Ler template de templates/<tipo>/".yellow());
    println!("{}", "  - Substituir variáveis ({{name}}, etc)".yellow());
    println!("{}", "  - Criar diretório e arquivos".yellow());
    println!("{}", "  - Adicionar ao workspace se necessário".yellow());

    Ok(())
}
