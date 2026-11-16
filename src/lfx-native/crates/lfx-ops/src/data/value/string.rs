//! [`AnyString`]: text that is inline when short and shared when long, and [`StringPool`].

use crate::data::maps::{HashSet, State};
use std::borrow::Borrow;
use std::fmt;
use std::sync::{Arc, OnceLock};

use serde::de::{DeserializeSeed, Deserializer, Visitor};

/// Immutable text. Short text is inline. Copies of long text share it.
#[derive(Debug, Clone)]
pub struct AnyString(Repr);

#[derive(Debug, Clone)]
enum Repr {
    /// At most [`INLINE`] bytes.
    Inline(compact_str::CompactString),
    /// Shorter than [`LONG`] bytes: one allocation.
    Mid(Arc<str>),
    /// At least [`LONG`] bytes, with room to keep its JSON spelling.
    Shared(Arc<Text>),
}

/// Text this long can keep its JSON spelling ([`AnyString::shared_ascii_json`]).
const LONG: usize = 256;

/// The longest text held inline: what `CompactString` holds without allocating.
const INLINE: usize = std::mem::size_of::<String>();

#[derive(Debug)]
struct Text {
    text: Box<str>,
    ascii_json: OnceLock<Box<[u8]>>,
}

impl PartialEq for AnyString {
    fn eq(&self, other: &Self) -> bool {
        match (&self.0, &other.0) {
            (Repr::Shared(a), Repr::Shared(b)) if Arc::ptr_eq(a, b) => return true,
            (Repr::Mid(a), Repr::Mid(b)) if Arc::ptr_eq(a, b) => return true,
            _ => {}
        }
        self.as_str() == other.as_str()
    }
}
impl Eq for AnyString {}
impl std::hash::Hash for AnyString {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.as_str().hash(state);
    }
}

impl AnyString {
    /// The text, borrowed.
    #[must_use]
    pub fn as_str(&self) -> &str {
        match &self.0 {
            Repr::Inline(text) => text.as_str(),
            Repr::Mid(text) => text,
            Repr::Shared(text) => &text.text,
        }
    }

    /// The cached JSON spelling of long shared text. Unshared text gets no
    /// cache, so it keeps no second copy.
    pub(crate) fn shared_ascii_json(&self) -> Option<&[u8]> {
        let Repr::Shared(shared) = &self.0 else {
            return None;
        };
        if self.len() < LONG {
            return None;
        }
        if let Some(encoded) = shared.ascii_json.get() {
            return Some(encoded);
        }
        if Arc::strong_count(shared) <= 1 {
            return None;
        }
        Some(shared.ascii_json.get_or_init(|| {
            let mut encoded = Vec::with_capacity(self.len() + 2);
            crate::data::json_out::write_str(
                &mut encoded,
                self,
                crate::data::json_out::Ascii::Escape,
            );
            encoded.into_boxed_slice()
        }))
    }
}

impl Default for AnyString {
    fn default() -> Self {
        Self(Repr::Inline(compact_str::CompactString::default()))
    }
}

impl std::ops::Deref for AnyString {
    type Target = str;
    fn deref(&self) -> &str {
        self.as_str()
    }
}
impl Borrow<str> for AnyString {
    fn borrow(&self) -> &str {
        self.as_str()
    }
}
impl AsRef<str> for AnyString {
    fn as_ref(&self) -> &str {
        self.as_str()
    }
}
impl From<&str> for AnyString {
    fn from(text: &str) -> Self {
        if text.len() <= INLINE {
            return Self(Repr::Inline(compact_str::CompactString::new(text)));
        }
        if text.len() < LONG {
            return Self(Repr::Mid(Arc::from(text)));
        }
        Self(Repr::Shared(Arc::new(Text {
            text: text.into(),
            ascii_json: OnceLock::new(),
        })))
    }
}
impl From<String> for AnyString {
    fn from(text: String) -> Self {
        if text.len() <= INLINE {
            return Self(Repr::Inline(compact_str::CompactString::new(&text)));
        }
        if text.len() < LONG {
            return Self(Repr::Mid(Arc::from(text)));
        }
        Self(Repr::Shared(Arc::new(Text {
            text: text.into_boxed_str(),
            ascii_json: OnceLock::new(),
        })))
    }
}
impl fmt::Display for AnyString {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self)
    }
}
impl PartialEq<str> for AnyString {
    fn eq(&self, other: &str) -> bool {
        self.as_str() == other
    }
}
impl PartialEq<&str> for AnyString {
    fn eq(&self, other: &&str) -> bool {
        self.as_str() == *other
    }
}

/// Text shared within one input. Separate inputs never share text.
#[derive(Debug, Default)]
pub struct StringPool {
    // Small inputs fit here, with no hash table to allocate.
    small: [Option<AnyString>; 16],
    large: Option<HashSet<AnyString>>,
}

impl StringPool {
    /// Reuse equal text, or allocate its first copy.
    pub fn intern(&mut self, text: &str) -> AnyString {
        // Short text is inline: a copy costs no more than a shared reference.
        if text.len() <= INLINE {
            return AnyString::from(text);
        }
        if let Some(strings) = &mut self.large {
            if let Some(shared) = strings.get(text) {
                return shared.clone();
            }
            let shared = AnyString::from(text);
            strings.insert(shared.clone());
            return shared;
        }
        for slot in &mut self.small {
            if let Some(shared) = slot {
                if shared.as_str() == text {
                    return shared.clone();
                }
            } else {
                let shared = AnyString::from(text);
                *slot = Some(shared.clone());
                return shared;
            }
        }
        #[expect(
            clippy::mutable_key_type,
            reason = "the JSON cache is excluded from equality and hashing"
        )]
        let mut strings = HashSet::with_capacity_and_hasher(self.small.len() * 2, State::default());
        strings.extend(self.small.iter_mut().filter_map(Option::take));
        self.large = Some(strings);
        self.intern(text)
    }
}

pub(super) struct StringSeed<'a>(pub(super) &'a mut StringPool);
impl<'de> DeserializeSeed<'de> for StringSeed<'_> {
    type Value = AnyString;
    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<AnyString, D::Error> {
        deserializer.deserialize_str(self)
    }
}
impl Visitor<'_> for StringSeed<'_> {
    type Value = AnyString;
    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("a string")
    }
    fn visit_str<E>(self, text: &str) -> Result<AnyString, E> {
        Ok(self.0.intern(text))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::value::AnyValue;
    use std::hash::BuildHasher;

    fn parse(text: &str) -> AnyValue {
        serde_json::from_str(text).unwrap()
    }

    /// Whether two strings share one allocation.
    fn shared(a: &AnyString, b: &AnyString) -> bool {
        match (&a.0, &b.0) {
            (Repr::Shared(x), Repr::Shared(y)) => Arc::ptr_eq(x, y),
            (Repr::Mid(x), Repr::Mid(y)) => Arc::ptr_eq(x, y),
            _ => false,
        }
    }

    /// Whether a string keeps its JSON spelling.
    fn cached(text: &AnyString) -> bool {
        matches!(&text.0, Repr::Shared(t) if t.ascii_json.get().is_some())
    }

    #[test]
    fn short_text_is_inline() {
        assert!(matches!(AnyString::from("value").0, Repr::Inline(_)));
        assert!(matches!(
            AnyString::from("x".repeat(INLINE + 1)).0,
            Repr::Mid(_)
        ));
        assert!(matches!(
            AnyString::from("x".repeat(LONG)).0,
            Repr::Shared(_)
        ));
    }

    #[test]
    fn a_pool_keeps_shared_text_when_it_grows_beyond_small_inputs() {
        let mut pool = StringPool::default();
        let first = pool.intern("first text, longer than inline text");
        for i in 0..32 {
            pool.intern(&format!("key-{i}, longer than inline text"));
        }
        let again = pool.intern("first text, longer than inline text");
        assert!(shared(&first, &again));
        drop(pool);
        assert_eq!(first.as_str(), "first text, longer than inline text");
        assert_eq!(again.as_str(), "first text, longer than inline text");
    }

    #[test]
    fn shared_json_cache_preserves_equality_hashes_and_thread_safety() {
        let mut pool = StringPool::default();
        let text = "code \"quoted\"\nœ 😀 ".repeat(50);
        let a = pool.intern(&text);
        let b = pool.intern(&text);
        drop(pool);
        let independent = AnyString::from(text.clone());
        let hash = std::collections::hash_map::RandomState::new();
        let before = hash.hash_one(&a);
        let threads: Vec<_> = [a.clone(), b.clone()]
            .into_iter()
            .map(|text| std::thread::spawn(move || crate::api::json_text(&AnyValue::String(text))))
            .collect();
        for thread in threads {
            let encoded = thread.join().unwrap();
            assert!(encoded.is_ascii());
            assert_eq!(serde_json::from_str::<String>(&encoded).unwrap(), text);
        }
        assert!(cached(&a));
        assert_eq!(a, independent);
        assert_eq!(hash.hash_one(&a), before);
        assert_eq!(hash.hash_one(&a), hash.hash_one(&independent));
    }

    #[test]
    fn unique_long_text_is_written_without_a_cache() {
        let text = AnyString::from("unique \"text\"\n".repeat(100));
        let value = AnyValue::String(text);
        let encoded = crate::api::json_text(&value);
        assert_eq!(serde_json::from_str::<AnyValue>(&encoded).unwrap(), value);
        let AnyValue::String(text) = value else {
            panic!("string");
        };
        assert!(!cached(&text));
    }

    #[test]
    fn parsed_keys_and_values_share_text_within_one_input() {
        let value = parse(
            r#"[{"repeated key, longer than inline text":"shared text, longer than inline"},{"repeated key, longer than inline text":"sh\u0061red text, longer than inline"}]"#,
        );
        let a = value[0].as_object().unwrap();
        let b = value[1].as_object().unwrap();
        let (ka, va) = a.iter().next().unwrap();
        let (kb, vb) = b.iter().next().unwrap();
        assert!(shared(ka, kb));
        let (AnyValue::String(va), AnyValue::String(vb)) = (va, vb) else {
            panic!("strings");
        };
        assert!(shared(va, vb));
        let mut copied = value.clone();
        copied[0]["repeated key, longer than inline text"] = AnyValue::from("changed");
        assert_eq!(
            value[0]["repeated key, longer than inline text"].as_str(),
            Some("shared text, longer than inline")
        );
        let AnyValue::String(unchanged) = &copied[1]["repeated key, longer than inline text"]
        else {
            panic!("string");
        };
        assert!(shared(va, unchanged));
    }
}
