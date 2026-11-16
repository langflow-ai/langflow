//! Every number in a stored flow is finite.

use crate::json::FlowValue;

use crate::json::is_finite_number;
use crate::json::pointer::{Step, owned_path};
use crate::violation::{Violation, ViolationCode};

/// Each number in `value` that is not finite, in document order.
pub(crate) fn non_finite_violations<'a>(
    value: &'a FlowValue,
    path: &mut Vec<Step<'a>>,
    violations: &mut Vec<Violation>,
) {
    match value {
        FlowValue::Number(number) if !is_finite_number(number) => violations.push(Violation::new(
            ViolationCode::NonFiniteNumber,
            owned_path(path),
            "NaN, Infinity and integers too large for a double are not valid JSON",
        )),
        FlowValue::Object(map) => {
            for (key, item) in map {
                path.push(Step::Key(key));
                non_finite_violations(item, path, violations);
                path.pop();
            }
        }
        FlowValue::Array(items) => {
            for (index, item) in items.iter().enumerate() {
                path.push(Step::Index(index));
                non_finite_violations(item, path, violations);
                path.pop();
            }
        }
        _ => {}
    }
}
