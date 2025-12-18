//! Builder module - Core build functionality
//!
//! Provides utilities for building Redstone OS components

use anyhow::{Context, Result};
use colored::*;
use std::path::{Path, PathBuf};
use std::process::Command;
use xshell::{cmd, Shell};

/// Get the project root directory
pub fn project_root() -> Result<PathBuf> {
    // Try CARGO_MANIFEST_DIR first (works during development)
    if let Ok(manifest_dir) = std::env::var("CARGO_MANIFEST_DIR") {
        let anvil_dir = PathBuf::from(manifest_dir);
        if let Some(root) = anvil_dir.parent() {
            return Ok(root.to_path_buf());
        }
    }

    // Fallback: search for Cargo.toml in current dir and parent dirs
    let mut current = std::env::current_dir().context("Failed to get current directory")?;

    loop {
        let cargo_toml = current.join("Cargo.toml");
        if cargo_toml.exists() {
            // Check if this is the workspace root by looking for [workspace]
            if let Ok(content) = std::fs::read_to_string(&cargo_toml) {
                if content.contains("[workspace]") {
                    return Ok(current);
                }
            }
        }

        // Try parent directory
        if let Some(parent) = current.parent() {
            current = parent.to_path_buf();
        } else {
            break;
        }
    }

    anyhow::bail!("Could not find project root (workspace Cargo.toml)")
}

/// Build a Rust package with specified target and profile
pub fn build_package(
    sh: &Shell,
    package: &str,
    target: &str,
    release: bool,
    verbose: bool,
) -> Result<()> {
    let root = project_root()?;
    let _dir = sh.push_dir(&root);

    let mut args = vec!["build", "-p", package, "--target", target];

    if release {
        args.push("--release");
    }

    if verbose {
        args.push("-vv");
    }

    println!(
        "   {} {} (target: {})",
        "→".bright_blue(),
        package.bright_cyan(),
        target.bright_black()
    );

    let output = Command::new("cargo")
        .args(&args)
        .output()
        .context("Failed to execute cargo")?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        eprintln!("{}", stderr);
        anyhow::bail!("Failed to build {}", package);
    }

    if verbose {
        let stdout = String::from_utf8_lossy(&output.stdout);
        println!("{}", stdout);
    }

    Ok(())
}

/// Copy a file from source to destination, creating parent directories
pub fn copy_file(src: &Path, dest: &Path, verbose: bool) -> Result<()> {
    if let Some(parent) = dest.parent() {
        std::fs::create_dir_all(parent)
            .context(format!("Failed to create directory: {}", parent.display()))?;
    }

    std::fs::copy(src, dest).context(format!(
        "Failed to copy {} to {}",
        src.display(),
        dest.display()
    ))?;

    if verbose {
        println!(
            "     {} {} → {}",
            "✓".bright_green(),
            src.display().to_string().bright_black(),
            dest.display().to_string().bright_cyan()
        );
    }

    Ok(())
}

/// Create a directory and all parent directories
pub fn create_dir_all(path: &Path, verbose: bool) -> Result<()> {
    std::fs::create_dir_all(path)
        .context(format!("Failed to create directory: {}", path.display()))?;

    if verbose {
        println!(
            "     {} {}",
            "📁".bright_blue(),
            path.display().to_string().bright_cyan()
        );
    }

    Ok(())
}

/// Get the target directory for a specific target triple
pub fn target_dir(target: &str, release: bool) -> Result<PathBuf> {
    let root = project_root()?;
    let profile = if release { "release" } else { "debug" };
    Ok(root.join("target").join(target).join(profile))
}

/// Get the dist directory
pub fn dist_dir() -> Result<PathBuf> {
    let root = project_root()?;
    Ok(root.join("dist"))
}
