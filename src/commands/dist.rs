//! Comando dist - Cria distribuição

use anyhow::{Context, Result};
use colored::*;
use std::path::PathBuf;

use crate::core::{builder, config, utils};

pub fn run(release: bool, recipe: Option<String>, verbose: bool) -> Result<()> {
    println!("{}", "📦 Criando distribuição...".bright_yellow());

    if let Some(r) = recipe {
        println!("   Receita: {}", r.bright_green());
        utils::print_warning(
            "Sistema de receitas ainda não implementado, usando configuração padrão",
        );
    }

    let profile = if release { "release" } else { "debug" };
    println!("   Perfil: {}", profile.bright_green());

    // Get directories
    let dist = builder::dist_dir()?;

    // Clean dist directory
    if dist.exists() {
        utils::print_step("Limpando diretório dist/...");
        std::fs::remove_dir_all(&dist).context("Failed to remove dist directory")?;
    }

    // Create directory structure
    utils::print_step("Criando estrutura de diretórios...");
    create_dist_structure(&dist, verbose)?;

    // Copy binaries
    utils::print_step("Copiando binários...");
    copy_bootloader(&dist, release, verbose)?;
    copy_kernel(&dist, release, verbose)?;
    copy_userspace(&dist, release, verbose)?;

    utils::print_success("Distribuição criada com sucesso!");
    println!(
        "   Localização: {}",
        dist.display().to_string().bright_cyan()
    );

    Ok(())
}

fn create_dist_structure(dist: &PathBuf, verbose: bool) -> Result<()> {
    let efi_boot = dist.join(config::dist_paths::efi_boot());
    let boot = dist.join(config::dist_paths::boot());
    let system_bin = dist.join(config::dist_paths::system_bin());
    let system_lib = dist.join(config::dist_paths::system_lib());

    builder::create_dir_all(&efi_boot, verbose)?;
    builder::create_dir_all(&boot, verbose)?;
    builder::create_dir_all(&system_bin, verbose)?;
    builder::create_dir_all(&system_lib, verbose)?;

    Ok(())
}

fn copy_bootloader(dist: &PathBuf, release: bool, verbose: bool) -> Result<()> {
    let target_dir = builder::target_dir(config::targets::UEFI, release)?;

    // UEFI bootloader is named after the package with .efi extension
    let src = target_dir.join(format!("{}.efi", config::packages::BOOTLOADER));
    let dest = dist
        .join(config::dist_paths::efi_boot())
        .join(config::binaries::BOOTLOADER_EFI);

    if !src.exists() {
        utils::print_warning(&format!(
            "Bootloader não encontrado em {}. Execute 'anvil build bootloader' primeiro.",
            src.display()
        ));
        return Ok(());
    }

    builder::copy_file(&src, &dest, verbose)?;
    Ok(())
}

fn copy_kernel(dist: &PathBuf, release: bool, verbose: bool) -> Result<()> {
    let target_dir = builder::target_dir(config::targets::KERNEL, release)?;
    let src = target_dir.join(config::packages::KERNEL);
    let dest = dist
        .join(config::dist_paths::boot())
        .join(config::binaries::KERNEL);

    if !src.exists() {
        utils::print_warning(&format!(
            "Kernel não encontrado em {}. Execute 'anvil build kernel' primeiro.",
            src.display()
        ));
        return Ok(());
    }

    builder::copy_file(&src, &dest, verbose)?;
    Ok(())
}

fn copy_userspace(dist: &PathBuf, release: bool, verbose: bool) -> Result<()> {
    let target_dir = builder::target_dir(config::targets::USERSPACE, release)?;

    // Copy init
    let init_src = target_dir.join(config::packages::INIT);
    let init_dest = dist
        .join(config::dist_paths::system_bin())
        .join(config::binaries::INIT);

    if init_src.exists() {
        builder::copy_file(&init_src, &init_dest, verbose)?;
    } else {
        utils::print_warning(&format!(
            "Init não encontrado em {}. Execute 'anvil build userspace' primeiro.",
            init_src.display()
        ));
    }

    // TODO: Copy stdlib and other userspace components as needed

    Ok(())
}
