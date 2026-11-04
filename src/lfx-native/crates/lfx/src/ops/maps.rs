//! Hash maps and sets with ahash instead of the standard library's `SipHash`.
//!
//! Every map of the engine is keyed by text from a flow: object keys and
//! ids of 20 to 300 bytes. `SipHash` made hashing a large part of reading a
//! graph and of each write. ahash is seeded from random keys, as `SipHash`
//! is, so a flow cannot choose keys that collide.

use std::hash::BuildHasher;
use std::sync::OnceLock;

/// ahash, seeded once per process from the standard library's random
/// keys, as the string pool seeds it.
#[derive(Debug, Clone)]
pub struct State(ahash::RandomState);

impl Default for State {
    fn default() -> Self {
        static SEEDS: OnceLock<[u64; 4]> = OnceLock::new();
        let [a, b, c, d] = *SEEDS.get_or_init(|| {
            let keys = std::collections::hash_map::RandomState::new();
            [0_u8, 1, 2, 3].map(|n| keys.hash_one(n))
        });
        Self(ahash::RandomState::with_seeds(a, b, c, d))
    }
}

impl BuildHasher for State {
    type Hasher = ahash::AHasher;
    fn build_hasher(&self) -> Self::Hasher {
        self.0.build_hasher()
    }
}

/// `std::collections::HashMap` with [`State`].
pub type HashMap<K, V> = std::collections::HashMap<K, V, State>;
/// `std::collections::HashSet` with [`State`].
pub type HashSet<K> = std::collections::HashSet<K, State>;
/// `indexmap::IndexMap` with [`State`].
pub type IndexMap<K, V> = indexmap::IndexMap<K, V, State>;
/// `indexmap::IndexSet` with [`State`].
pub type IndexSet<K> = indexmap::IndexSet<K, State>;
