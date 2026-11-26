"""Default archive transformation for declared references."""

from copy import deepcopy

from lfx.projects.references import field_references


def remap_declared_references(definition, config, mapping):
    result = deepcopy(config)
    if result is None:
        return None
    for field in definition.fields:
        if not field.references or field.name not in result:
            continue
        references = field_references(field, result[field.name])
        values = [
            {**reference.model_dump(mode="json"), "project_id": mapping.project_ids[str(reference.project_id)]}
            for reference in references
        ]
        result[field.name] = values if getattr(field.input, "is_list", False) else values[0] if values else None
    return result
