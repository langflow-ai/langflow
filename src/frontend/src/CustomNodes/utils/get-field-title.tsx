import type { APITemplateType } from "../../types/api";
import { translateNodeField } from "@/i18n/nodeTranslations";

export default function getFieldTitle(
  template: APITemplateType,
  templateField: string,
): string {
  const rawTitle = template[templateField].display_name
    ? template[templateField].display_name!
    : (template[templateField].name ?? templateField);
  return translateNodeField(rawTitle);
}
