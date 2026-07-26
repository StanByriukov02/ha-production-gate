use std::env;
use std::path::PathBuf;

fn main() {
    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let c_dir = manifest.join("c");
    println!("cargo:rerun-if-changed={}", c_dir.join("ha_silicon_fuse.c").display());
    println!("cargo:rerun-if-changed={}", c_dir.join("ha_silicon_fuse.h").display());
    cc::Build::new()
        .file(c_dir.join("ha_silicon_fuse.c"))
        .include(&c_dir)
        .warnings(true)
        .compile("ha_silicon_fuse_c");
}
