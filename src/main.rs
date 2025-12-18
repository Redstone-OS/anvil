//! Anvil - Build System do Redstone OS
//!
//! A bigorna onde forjamos o Redstone OS.
//!
//! # Trocadilho
//! - Ignite (bootloader) = Acende a forja
//! - Forge (kernel) = A forja
//! - Anvil (build tool) = A bigorna
//! - Redstone = A pedra vermelha
//!
//! # Uso
//! ```bash
//! anvil build --release
//! anvil run
//! anvil dist
//! ```

use anyhow::Result;
use clap::{Parser, Subcommand};
use colored::*;

mod commands;
mod core;

#[derive(Parser)]
#[command(name = "anvil")]
#[command(about = "🔨 Anvil - A bigorna onde forjamos o Redstone OS", long_about = None)]
#[command(version)]
struct Cli {
    #[command(subcommand)]
    command: Commands,

    /// Verbose output
    #[arg(short, long, global = true)]
    verbose: bool,

    /// Quiet mode
    #[arg(short, long, global = true)]
    quiet: bool,
}

#[derive(Subcommand)]
enum Commands {
    /// Compila o sistema
    Build {
        /// Modo release
        #[arg(short, long)]
        release: bool,

        /// Target específico (kernel, bootloader, drivers, userspace)
        target: Option<String>,
    },

    /// Executa no QEMU
    Run {
        /// Modo release
        #[arg(short, long)]
        release: bool,

        /// Habilita GDB server
        #[arg(long)]
        gdb: bool,

        /// Habilita KVM
        #[arg(long)]
        kvm: bool,
    },

    /// Cria distribuição
    Dist {
        /// Modo release
        #[arg(short, long)]
        release: bool,

        /// Receita a usar
        #[arg(long)]
        recipe: Option<String>,
    },

    /// Cria ISO bootável
    Iso {
        /// Receita a usar
        #[arg(long)]
        recipe: Option<String>,
    },

    /// Grava em USB
    Usb {
        /// Dispositivo (ex: /dev/sdb)
        #[arg(long)]
        device: Option<String>,
    },

    /// Gerencia receitas
    Recipe {
        #[command(subcommand)]
        action: RecipeAction,
    },

    /// Gerencia templates
    Template {
        #[command(subcommand)]
        action: TemplateAction,
    },

    /// Verifica código
    Check,

    /// Formata código
    Fmt,

    /// Linter
    Clippy,

    /// Gera documentação
    Doc {
        /// Abre no browser
        #[arg(long)]
        open: bool,
    },

    /// Limpa artefatos
    Clean {
        /// Limpa tudo (incluindo cache)
        #[arg(long)]
        all: bool,
    },

    /// Mostra ambiente
    Env,
}

#[derive(Subcommand)]
enum RecipeAction {
    /// Lista receitas
    List,
    /// Mostra receita
    Show { name: String },
    /// Usa receita
    Use { name: String },
}

#[derive(Subcommand)]
enum TemplateAction {
    /// Lista templates
    List,
    /// Cria novo componente
    New {
        /// Tipo (driver, service, app, lib)
        template_type: String,
        /// Nome
        name: String,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    // Banner
    if !cli.quiet {
        println!("{}", "🔨 Anvil - Build System do Redstone OS".bright_cyan().bold());
        println!("{}", "   A bigorna onde forjamos o sistema".bright_black());
        println!();
    }

    match cli.command {
        Commands::Build { release, target } => {
            commands::build::run(release, target, cli.verbose)?;
        }
        Commands::Run { release, gdb, kvm } => {
            commands::run::run(release, gdb, kvm, cli.verbose)?;
        }
        Commands::Dist { release, recipe } => {
            commands::dist::run(release, recipe, cli.verbose)?;
        }
        Commands::Iso { recipe } => {
            commands::iso::run(recipe, cli.verbose)?;
        }
        Commands::Usb { device } => {
            commands::usb::run(device, cli.verbose)?;
        }
        Commands::Recipe { action } => match action {
            RecipeAction::List => commands::recipe::list(cli.verbose)?,
            RecipeAction::Show { name } => commands::recipe::show(&name, cli.verbose)?,
            RecipeAction::Use { name } => commands::recipe::use_recipe(&name, cli.verbose)?,
        },
        Commands::Template { action } => match action {
            TemplateAction::List => commands::template::list(cli.verbose)?,
            TemplateAction::New { template_type, name } => {
                commands::template::new(&template_type, &name, cli.verbose)?
            }
        },
        Commands::Check => commands::check::run(cli.verbose)?,
        Commands::Fmt => commands::fmt::run(cli.verbose)?,
        Commands::Clippy => commands::clippy::run(cli.verbose)?,
        Commands::Doc { open } => commands::doc::run(open, cli.verbose)?,
        Commands::Clean { all } => commands::clean::run(all, cli.verbose)?,
        Commands::Env => commands::env::run(cli.verbose)?,
    }

    Ok(())
}
