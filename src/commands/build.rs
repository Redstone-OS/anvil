//! Comando build - Compila o sistema

use anyhow::Result;
use colored::*;
use xshell::Shell;

use crate::core::{builder, config, utils};

pub fn run(release: bool, target: Option<String>, verbose: bool) -> Result<()> {
    println!("{}", "🔨 Forjando o Redstone OS...".bright_yellow());

    let profile = if release { "release" } else { "debug" };
    println!("   Perfil: {}", profile.bright_green());

    let sh = Shell::new()?;

    if let Some(t) = target {
        println!("   Target: {}", t.bright_green());
        match t.as_str() {
            "kernel" => build_kernel(release, verbose, &sh)?,
            "bootloader" => build_bootloader(release, verbose, &sh)?,
            "drivers" => build_drivers(release, verbose, &sh)?,
            "userspace" => build_userspace(release, verbose, &sh)?,
            _ => {
                eprintln!("{}", format!("Target desconhecido: {}", t).red());
                return Ok(());
            }
        }
    } else {
        // Build completo
        build_all(release, verbose, &sh)?;
    }

    println!("{}", "✓ Build concluído!".bright_green().bold());
    Ok(())
}

fn build_all(release: bool, verbose: bool, sh: &Shell) -> Result<()> {
    build_bootloader(release, verbose, sh)?;
    build_kernel(release, verbose, sh)?;
    build_userspace(release, verbose, sh)?;
    // Drivers são opcionais para boot mínimo
    // build_drivers(release, verbose, sh)?;
    Ok(())
}

fn build_kernel(release: bool, verbose: bool, sh: &Shell) -> Result<()> {
    utils::print_step("Compilando Kernel (Forge)...");

    builder::build_package(
        sh,
        config::packages::KERNEL,
        config::targets::KERNEL,
        release,
        verbose,
    )?;

    utils::print_success("Kernel compilado");
    Ok(())
}

fn build_bootloader(release: bool, verbose: bool, sh: &Shell) -> Result<()> {
    utils::print_step("Compilando Bootloader (Ignite)...");

    builder::build_package(
        sh,
        config::packages::BOOTLOADER,
        config::targets::UEFI,
        release,
        verbose,
    )?;

    utils::print_success("Bootloader compilado");
    Ok(())
}

fn build_userspace(release: bool, verbose: bool, sh: &Shell) -> Result<()> {
    utils::print_step("Compilando Userspace...");

    // Build init
    builder::build_package(
        sh,
        config::packages::INIT,
        config::targets::USERSPACE,
        release,
        verbose,
    )?;

    // Build stdlib (library, não precisa de target específico)
    // Comentado por enquanto pois stdlib pode não ter binary
    // builder::build_package(
    //     sh,
    //     config::packages::STDLIB,
    //     config::targets::USERSPACE,
    //     release,
    //     verbose,
    // )?;

    utils::print_success("Userspace compilado");
    Ok(())
}

fn build_drivers(_release: bool, _verbose: bool, _sh: &Shell) -> Result<()> {
    utils::print_step("Compilando Drivers...");
    // TODO(prioridade=média, versão=v1.0): Implementar build dos drivers
    utils::print_warning("Build de drivers ainda não implementado");
    Ok(())
}
