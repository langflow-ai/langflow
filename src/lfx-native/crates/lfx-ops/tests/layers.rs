//! Each folder of `src` imports only from the folders before it:
//! `map`, `json`, `flow`, `compare`, `node_input`, `violation`,
//! `invariant`, `rule`, `validate.rs`, `snapshot`, `state`, `op`, then `api.rs`.
//!
//! Tests may import from any folder, so the check stops at `#[cfg(test)]`
//! and skips `tests.rs` files.

use std::fs;
use std::path::{Path, PathBuf};

const LAYERS: [&str; 13] = [
    "map",
    "json",
    "flow",
    "compare",
    "node_input",
    "violation",
    "invariant",
    "rule",
    "validate",
    "snapshot",
    "state",
    "op",
    "api",
];

fn layer(name: &str) -> Option<usize> {
    LAYERS.iter().position(|layer| *layer == name)
}

/// Every `.rs` file under `dir`.
fn rust_files(dir: &Path, out: &mut Vec<PathBuf>) {
    for entry in fs::read_dir(dir).expect("src is readable") {
        let path = entry.expect("src is readable").path();
        if path.is_dir() {
            rust_files(&path, out);
        } else if path.extension().is_some_and(|ext| ext == "rs") {
            out.push(path);
        }
    }
}

#[test]
fn each_folder_imports_only_from_the_folders_before_it() {
    let src = Path::new(env!("CARGO_MANIFEST_DIR")).join("src");
    let mut files = Vec::new();
    rust_files(&src, &mut files);
    let mut wrong = Vec::new();
    for file in files {
        let relative = file.strip_prefix(&src).unwrap();
        let top = relative.iter().next().unwrap().to_str().unwrap();
        let Some(own) = layer(top.trim_end_matches(".rs")) else {
            continue;
        };
        if relative.ends_with("tests.rs") {
            continue;
        }
        let text = fs::read_to_string(&file).unwrap();
        for (number, line) in text.lines().enumerate() {
            if line == "#[cfg(test)]" {
                break;
            }
            if line.trim_start().starts_with("//") {
                continue;
            }
            for (at, _) in line.match_indices("crate::") {
                let name: String = line[at + "crate::".len()..]
                    .chars()
                    .take_while(|c| c.is_alphanumeric() || *c == '_')
                    .collect();
                if layer(&name).is_some_and(|used| used > own) {
                    wrong.push(format!("{}:{}: {line}", relative.display(), number + 1));
                }
            }
        }
    }
    assert!(
        wrong.is_empty(),
        "imports from a later folder:\n{}",
        wrong.join("\n")
    );
}
