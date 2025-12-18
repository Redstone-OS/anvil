//! Utilities module - General utility functions

use colored::*;

/// Print a step message
pub fn print_step(message: &str) {
    println!("   {} {}", "→".bright_blue(), message);
}

/// Print a success message
pub fn print_success(message: &str) {
    println!("   {} {}", "✓".bright_green(), message);
}

/// Print an error message
pub fn print_error(message: &str) {
    eprintln!("   {} {}", "✗".bright_red(), message);
}

/// Print a warning message
pub fn print_warning(message: &str) {
    println!("   {} {}", "⚠".bright_yellow(), message);
}

/// Print an info message
pub fn print_info(message: &str) {
    println!("   {} {}", "ℹ".bright_cyan(), message);
}
