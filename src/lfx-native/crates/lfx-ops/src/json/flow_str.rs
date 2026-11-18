//! [`FlowStr`]: text that is inline when short and shared when long, and [`StringPool`].

use crate::map::hash::{HashSet, State};
use std::borrow::Borrow;
use std::fmt;
use std::sync::{Arc, OnceLock};

use serde::de::{DeserializeSeed, Deserializer, Visitor};

/// Immutable text. Short text is inline. Copies of long text share it.
#[derive(Debug, Clone)]
pub struct FlowStr(Repr);

#[derive(Debug, Clone)]
enum Repr {
    /// At most [`INLINE`] bytes.
    Inline(compact_str::CompactString),
    /// Shorter than [`LONG`] bytes: one allocation.
    Mid(Arc<str>),
    /// At least [`LONG`] bytes, with room to keep its JSON spelling.
    Shared(Arc<Text>),
}

/// Text this long can keep its JSON spelling ([`FlowStr::shared_ascii_json`]).
const LONG: usize = 256;

/// The longest text held inline: what `CompactString` holds without allocating.
const INLINE: usize = std::mem::size_of::<String>();

#[derive(Debug)]
struct Text {
    text: Box<str>,
    ascii_json: OnceLock<Box<[u8]>>,
}

impl PartialEq for FlowStr {
    fn eq(&self, other: &Self) -> bool {
        match (&self.0, &other.0) {
            (Repr::Shared(a), Repr::Shared(b)) if Arc::ptr_eq(a, b) => return true,
            (Repr::Mid(a), Repr::Mid(b)) if Arc::ptr_eq(a, b) => return true,
            _ => {}
        }
        self.as_str() == other.as_str()
    }
}
impl Eq for FlowStr {}
impl std::hash::Hash for FlowStr {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.as_str().hash(state);
    }
}

impl FlowStr {
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
            crate::json::serialize::write_str(
                &mut encoded,
                self,
                crate::json::serialize::Ascii::Escape,
            );
            encoded.into_boxed_slice()
        }))
    }
}

impl Default for FlowStr {
    fn default() -> Self {
        Self(Repr::Inline(compact_str::CompactString::default()))
    }
}

impl std::ops::Deref for FlowStr {
    type Target = str;
    fn deref(&self) -> &str {
        self.as_str()
    }
}
impl Borrow<str> for FlowStr {
    fn borrow(&self) -> &str {
        self.as_str()
    }
}
impl AsRef<str> for FlowStr {
    fn as_ref(&self) -> &str {
        self.as_str()
    }
}
impl From<&str> for FlowStr {
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
impl From<String> for FlowStr {
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
impl fmt::Display for FlowStr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self)
    }
}
impl PartialEq<str> for FlowStr {
    fn eq(&self, other: &str) -> bool {
        self.as_str() == other
    }
}
impl PartialEq<&str> for FlowStr {
    fn eq(&self, other: &&str) -> bool {
        self.as_str() == *other
    }
}

/// Text shared within one input. Separate inputs never share text.
#[derive(Debug, Default)]
pub struct StringPool {
    // Small inputs fit here, with no hash table to allocate.
    small: [Option<FlowStr>; 16],
    large: Option<HashSet<FlowStr>>,
}

impl StringPool {
    /// Reuse equal text, or allocate its first copy.
    pub fn intern(&mut self, text: &str) -> FlowStr {
        // Short text is inline: a copy costs no more than a shared reference.
        if text.len() <= INLINE {
            return FlowStr::from(text);
        }
        if let Some(strings) = &mut self.large {
            if let Some(shared) = strings.get(text) {
                return shared.clone();
            }
            let shared = FlowStr::from(text);
            strings.insert(shared.clone());
            return shared;
        }
        for entry in &mut self.small {
            if let Some(shared) = entry {
                if shared.as_str() == text {
                    return shared.clone();
                }
            } else {
                let shared = FlowStr::from(text);
                *entry = Some(shared.clone());
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

pub(crate) struct StringSeed<'a>(pub(crate) &'a mut StringPool);
impl<'de> DeserializeSeed<'de> for StringSeed<'_> {
    type Value = FlowStr;
    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<FlowStr, D::Error> {
        deserializer.deserialize_str(self)
    }
}
impl Visitor<'_> for StringSeed<'_> {
    type Value = FlowStr;
    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("a string")
    }
    fn visit_str<E>(self, text: &str) -> Result<FlowStr, E> {
        Ok(self.0.intern(text))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::json::FlowValue;
    use std::hash::BuildHasher;

    fn parse(text: &str) -> FlowValue {
        serde_json::from_str(text).unwrap()
    }

    /// Whether two strings share one allocation.
    fn shared(a: &FlowStr, b: &FlowStr) -> bool {
        match (&a.0, &b.0) {
            (Repr::Shared(x), Repr::Shared(y)) => Arc::ptr_eq(x, y),
            (Repr::Mid(x), Repr::Mid(y)) => Arc::ptr_eq(x, y),
            _ => false,
        }
    }

    /// Whether a string keeps its JSON spelling.
    fn cached(text: &FlowStr) -> bool {
        matches!(&text.0, Repr::Shared(t) if t.ascii_json.get().is_some())
    }

    #[test]
    fn short_text_is_inline() {
        assert!(matches!(FlowStr::from("value").0, Repr::Inline(_)));
        assert!(matches!(
            FlowStr::from("x".repeat(INLINE + 1)).0,
            Repr::Mid(_)
        ));
        assert!(matches!(FlowStr::from("x".repeat(LONG)).0, Repr::Shared(_)));
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
        let independent = FlowStr::from(text.clone());
        let hash = std::collections::hash_map::RandomState::new();
        let before = hash.hash_one(&a);
        let threads: Vec<_> = [a.clone(), b.clone()]
            .into_iter()
            .map(|text| {
                std::thread::spawn(move || crate::bindings::json_text(&FlowValue::String(text)))
            })
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
        let text = FlowStr::from("unique \"text\"\n".repeat(100));
        let value = FlowValue::String(text);
        let encoded = crate::bindings::json_text(&value);
        assert_eq!(serde_json::from_str::<FlowValue>(&encoded).unwrap(), value);
        let FlowValue::String(text) = value else {
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
        let (FlowValue::String(va), FlowValue::String(vb)) = (va, vb) else {
            panic!("strings");
        };
        assert!(shared(va, vb));
        let mut copied = value.clone();
        copied[0]["repeated key, longer than inline text"] = FlowValue::from("changed");
        assert_eq!(
            value[0]["repeated key, longer than inline text"].as_str(),
            Some("shared text, longer than inline")
        );
        let FlowValue::String(unchanged) = &copied[1]["repeated key, longer than inline text"]
        else {
            panic!("string");
        };
        assert!(shared(va, unchanged));
    }
}
