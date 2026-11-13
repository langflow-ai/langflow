//! Runs every shared golden fixture file against the engine, one test per case.
//!
//! The fixture files in `src/lfx-native/fixtures/` are the engine's
//! specification. Every runtime runs all of them: this runner, and the
//! runners of the Python and browser bindings.

mod apply;
mod canonical;
mod diff;
mod editor;
mod repair;
mod support;
mod tables;
mod validate;
mod write;

use libtest_mimic::{Arguments, Trial};

fn main() {
    let arguments = Arguments::from_args();
    let trials: Vec<Trial> = [
        support::trials(),
        apply::trials(),
        canonical::trials(),
        diff::trials(),
        editor::trials(),
        repair::trials(),
        tables::trials(),
        validate::trials(),
        write::trials(),
    ]
    .into_iter()
    .flatten()
    .collect();
    libtest_mimic::run(&arguments, trials).exit();
}
