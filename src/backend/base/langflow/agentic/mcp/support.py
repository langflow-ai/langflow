import math


def replace_none_and_null_with_empty_str(data: list[dict], required_fields: list[str] | None = None) -> list[dict]:
    """Replaces all None, 'null' (case-insensitive), and NaN/NaT float values with empty strings in a list of dicts.

    Args:
        data: List of dictionaries.1
        required_fields: List of field names that must be present in each dictionary.
                        Missing fields will be added with value "Not available".

    Returns:
        List of dictionaries with None, 'null', and NaN/NaT values replaced with "",
        and "NaN", "Infinity", "-Infinity" string values replaced with None.
    """
    not_avail = "Not available"

    # Precompute required set only once for all items, avoid recomputation per item
    required_fields_set = set(required_fields) if required_fields else None

    # Avoid set lookups per call by using a tuple for string comparisons
    str_nulls = {"null", "nan", "infinity", "-infinity"}

    def convert_value(v):
        if v is None:
            return not_avail
        # Check for string and strip/compare only if it's a string
        if isinstance(v, str):
            v_stripped = v.strip().lower()
            if v_stripped in str_nulls:
                return not_avail
        # Use math.isnan only if v is actually a float
        elif isinstance(v, float):
            if math.isnan(v):
                return not_avail
        # Optimize for pandas/numpy Timestamp/NaT etc., avoids hasattr on every object
        elif getattr(v, "isnat", False):
            return not_avail
        return v

    result_append = result = []
    # Use local vars to speed up lookups inside loop
    for d in data:
        if not isinstance(d, dict):
            result_append.append(d)
            continue
        new_dict = {k: convert_value(v) for k, v in d.items()}
        if required_fields_set:
            # Only check missing if required fields passed, avoid pointless ops
            missing = required_fields_set.difference(new_dict.keys())
            # Each missing is set only if really missing, minimizing loop
            if missing:
                for k in missing:
                    new_dict[k] = not_avail
        result_append.append(new_dict)
    return result
