//! Edge handles. An edge holds each handle twice: as an object in `data`,
//! and as a string where `œ` stands for `"`.

use crate::json::serialize::{self, Ascii};
use crate::json::{FlowObj, FlowValue};

/// The quote character of an edge handle's string form.
pub const HANDLE_QUOTE: char = 'œ';
/// The keys of an edge's two handles.
pub const HANDLE_KEYS: [&str; 2] = ["sourceHandle", "targetHandle"];

/// The object a handle string encodes, or `None`. Like `JSON.parse`, it
/// refuses `NaN` and `Infinity`.
#[must_use]
pub fn parse_handle(handle: &FlowValue) -> Option<FlowObj> {
    let text = handle.as_str()?.replace(HANDLE_QUOTE, "\"");
    match serde_json::from_str(&text) {
        Ok(FlowValue::Object(object)) => Some(object),
        _ => None,
    }
}

/// Whether `handle` is `object` written as a handle, so a caller can skip
/// [`parse_handle`]. Example: `{œidœ: œaœ}` and `{œidœ:œaœ}` spell `{"id": "a"}`.
/// A `false` does not mean the handle encodes another object.
#[must_use]
pub fn handle_spells(handle: &str, object: &FlowObj) -> bool {
    // Leave a number that is not finite to [`values_equal`], which refuses it.
    fn finite(value: &FlowValue) -> bool {
        match value {
            FlowValue::Number(number) => number.as_f64().is_some_and(f64::is_finite),
            FlowValue::Array(items) => items.iter().all(finite),
            FlowValue::Object(map) => map.values().all(finite),
            _ => true,
        }
    }
    if !object.values().all(finite) {
        return false;
    }
    let mut text = Vec::with_capacity(handle.len());
    serialize::write_map(&mut text, object, Ascii::Keep);
    let mut quote = [0; 4];
    let quote = HANDLE_QUOTE.encode_utf8(&mut quote).as_bytes();
    let mut handle = handle.as_bytes();
    let (mut in_string, mut escaped) = (false, false);
    // Each `œ` of the handle reads as `"`, so a `œ` in `object` cannot match.
    for &byte in &text {
        if let Some(after) = handle.strip_prefix(quote) {
            if byte != b'"' {
                return false;
            }
            handle = after;
        } else if handle.first() == Some(&byte) {
            handle = &handle[1..];
        } else {
            return false;
        }
        if in_string {
            if escaped {
                escaped = false;
            } else if byte == b'\\' {
                escaped = true;
            } else if byte == b'"' {
                in_string = false;
            }
        } else if byte == b'"' {
            in_string = true;
        } else if byte == b':' || byte == b',' {
            // Space between tokens does not change what the text encodes.
            handle = handle.strip_prefix(b" ").unwrap_or(handle);
        }
    }
    handle.is_empty()
}

/// A handle's string form: compact JSON with `œ` standing for `"`.
#[must_use]
pub fn escape_handle(handle: &FlowValue) -> String {
    handle.to_string().replace('"', &HANDLE_QUOTE.to_string())
}

/// Write each handle's missing form from the form that is present.
pub fn derive_missing_handle_forms(edge: &mut FlowObj) {
    if !edge.contains_key("data") {
        edge.insert("data".into(), FlowValue::Object(FlowObj::new()));
    }
    for key in HANDLE_KEYS {
        let object = edge["data"].get(key).cloned();
        match object {
            Some(object) if !edge.contains_key(key) => {
                edge.insert(key.into(), FlowValue::from(escape_handle(&object)));
            }
            None => {
                if let Some(parsed) = edge.get(key).and_then(parse_handle)
                    && let Some(FlowValue::Object(data)) = edge.get_mut("data")
                {
                    data.insert(key.into(), FlowValue::Object(parsed));
                }
            }
            Some(_) => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::json;

    use super::*;
    use crate::compare::values_equal;

    #[test]
    fn a_handle_spells_its_object_only_when_it_encodes_it() {
        let object = |text: &str| -> FlowObj {
            match serde_json::from_str(text).unwrap() {
                FlowValue::Object(map) => map,
                _ => unreachable!(),
            }
        };
        let handle = object(
            r#"{"dataType": "Prompt", "id": "P-1", "name": "prompt", "output_types": ["Message"]}"#,
        );
        // Both spellings a handle is written in, and a `"` that reads as itself.
        for text in [
            "{œdataTypeœ: œPromptœ, œidœ: œP-1œ, œnameœ: œpromptœ, œoutput_typesœ: [œMessageœ]}",
            "{œdataTypeœ:œPromptœ,œidœ:œP-1œ,œnameœ:œpromptœ,œoutput_typesœ:[œMessageœ]}",
            "{\"dataTypeœ:œPromptœ,œidœ:œP-1œ,œnameœ:œpromptœ,œoutput_typesœ:[œMessageœ]}",
        ] {
            assert!(handle_spells(text, &handle), "{text}");
            let parsed = parse_handle(&FlowValue::String(text.into())).unwrap();
            assert!(
                values_equal(
                    &FlowValue::Object(parsed),
                    &FlowValue::Object(handle.clone())
                )
                .unwrap()
            );
        }
        // Other text is left to the parse, which decides.
        for text in [
            "{œidœ: œP-1œ, œdataTypeœ: œPromptœ, œnameœ: œpromptœ, œoutput_typesœ: [œMessageœ]}",
            "{ œdataTypeœ: œPromptœ, œidœ: œP-1œ, œnameœ: œpromptœ, œoutput_typesœ: [œMessageœ]}",
            "{œdataTypeœ:  œPromptœ, œidœ: œP-1œ, œnameœ: œpromptœ, œoutput_typesœ: [œMessageœ]}",
            "{œdataTypeœ: œPromptœ, œidœ: œP-2œ, œnameœ: œpromptœ, œoutput_typesœ: [œMessageœ]}",
            "{œdataTypeœ: œPromptœ, œidœ: œP-1œ, œnameœ: œpromptœ, œoutput_typesœ: [œMessageœ]} ",
        ] {
            assert!(!handle_spells(text, &handle), "{text}");
        }
        // A space inside a string is text, not spacing.
        let spaced = object(r#"{"name": "a b"}"#);
        assert!(handle_spells("{œnameœ: œa bœ}", &spaced));
        assert!(!handle_spells("{œnameœ: œa  bœ}", &spaced));
        // An `œ` in the object cannot be spelled: the handle's `œ` reads as `"`.
        assert!(!handle_spells(
            "{œnameœ: œaœbœ}",
            &object(r#"{"name": "aœb"}"#)
        ));
        // A number that is not finite is left to `values_equal`, which refuses it.
        assert!(!handle_spells("{œnœ: 1e400}", &object(r#"{"n": 1e400}"#)));
    }

    #[test]
    fn handles_parse_strictly() {
        assert_eq!(
            parse_handle(&json!("{œnameœ:œoutœ}")),
            Some(json!({"name": "out"}).as_object().unwrap().clone())
        );
        assert_eq!(parse_handle(&json!("{œaœ:NaN}")), None);
        assert_eq!(parse_handle(&json!("[1]")), None);
        assert_eq!(parse_handle(&json!(1)), None);
    }
}
