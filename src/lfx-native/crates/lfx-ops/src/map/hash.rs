//! Hash maps and sets with ahash instead of `SipHash`.
//!
//! `SipHash` made hashing a large part of each read and write. ahash also
//! has random seeds, so a flow cannot choose keys that collide.

/// ahash, with seeds from the operating system's random source.
pub type State = ahash::RandomState;

/// `std::collections::HashMap` with [`State`].
pub type HashMap<K, V> = std::collections::HashMap<K, V, State>;
/// `std::collections::HashSet` with [`State`].
pub type HashSet<K> = std::collections::HashSet<K, State>;
/// `indexmap::IndexMap` with [`State`].
pub type IndexMap<K, V> = indexmap::IndexMap<K, V, State>;
/// `indexmap::IndexSet` with [`State`].
pub type IndexSet<K> = indexmap::IndexSet<K, State>;
