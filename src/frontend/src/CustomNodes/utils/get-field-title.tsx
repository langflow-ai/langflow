import type { APITemplateType } from "../../types/api";

export default function getFieldTitle(
  template: APITemplateType,
  templateField: string,
): string {
  return template[templateField].display_name
    ? template[templateField].display_name!
    : (template[templateField].name ?? templateField);
}
