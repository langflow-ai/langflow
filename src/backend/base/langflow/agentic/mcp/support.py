import math

from lfx.log.logger import logger


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
    # Precompute sets and string
    null_strs = {"null", "nan", "infinity", "-infinity"}
    not_avail = "Not available"
    required_fields_set = set(required_fields) if required_fields else None

    def convert_value(v):
        if v is None:
            return not_avail
        if isinstance(v, str):
            v_stripped = v.strip().lower()
            if v_stripped in null_strs:
                return not_avail
        elif isinstance(v, float):
            try:
                if math.isnan(v):
                    return not_avail
            except Exception as e:  # noqa: BLE001
                logger.aexception(f"Error converting value {v} to float: {e}")
        # Optimization: avoid getattr if not needed
        elif hasattr(v, "isnat"):
            isnat = getattr(v, "isnat", False)
            if isnat:
                return not_avail
        return v

    # Use list comprehension for fast iteration and avoid repeated set()-construction
    result: list[dict] = []
    if required_fields_set:
        for d in data:
            if not isinstance(d, dict):
                result.append(d)
                continue
            new_dict = {k: convert_value(v) for k, v in d.items()}
            # Only run if required_fields_set is not empty
            missing = required_fields_set - new_dict.keys()
            if missing:
                # Use dict.update for efficiency when adding more than one key
                for k in missing:
                    new_dict[k] = not_avail
            result.append(new_dict)
    else:
        # Avoid computing missing keys when not needed
        for d in data:
            if not isinstance(d, dict):
                result.append(d)
                continue
            new_dict = {k: convert_value(v) for k, v in d.items()}
            result.append(new_dict)
    return result
