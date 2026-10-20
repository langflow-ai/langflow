import type { APITemplateType } from "@/types/api";

/**
 * The template a template request returns, with the node's own `is_refresh`.
 *
 * A request tells the backend whether a refresh button was pressed by setting
 * `is_refresh` in the template it sends, and the backend sends that template
 * back. The flag belongs to that one request, not to the node. Applied as it
 * comes back, it changes the node, so the next save records it as an edit
 * ("Edited Is refresh"). `stored` is the node's template before the request.
 */
export function withStoredRefreshFlag(
  stored: APITemplateType | undefined,
  returned: APITemplateType,
): APITemplateType {
  const { is_refresh: _sent, ...template } = returned;
  if (stored && "is_refresh" in stored) {
    template.is_refresh = stored.is_refresh;
  }
  return template;
}
