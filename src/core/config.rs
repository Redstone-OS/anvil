//! Configuration module - Build configuration and constants

/// Build targets
pub mod targets {
    /// UEFI bootloader target
    pub const UEFI: &str = "x86_64-unknown-uefi";
    
    /// Kernel target (bare metal)
    pub const KERNEL: &str = "x86_64-unknown-none";
    
    /// Userspace target (same as kernel for now)
    pub const USERSPACE: &str = "x86_64-unknown-none";
}

/// Package names
pub mod packages {
    /// Bootloader package
    pub const BOOTLOADER: &str = "ignite";
    
    /// Kernel package
    pub const KERNEL: &str = "forge";
    
    /// Init service package
    pub const INIT: &str = "init";
    
    /// Standard library package
    pub const STDLIB: &str = "stdlib";
}

/// Distribution paths
pub mod dist_paths {
    use std::path::PathBuf;

    /// EFI boot directory
    pub fn efi_boot() -> PathBuf {
        PathBuf::from("EFI/BOOT")
    }

    /// Boot directory (for kernel)
    pub fn boot() -> PathBuf {
        PathBuf::from("boot")
    }

    /// System binaries directory
    pub fn system_bin() -> PathBuf {
        PathBuf::from("system/bin")
    }

    /// System libraries directory
    pub fn system_lib() -> PathBuf {
        PathBuf::from("system/lib")
    }
}

/// Binary names
pub mod binaries {
    /// UEFI bootloader binary name
    pub const BOOTLOADER_EFI: &str = "BOOTX64.EFI";
    
    /// Kernel binary name
    pub const KERNEL: &str = "forge";
    
    /// Init binary name
    pub const INIT: &str = "init";
}
