import type { APIClassType, APIDataType, InputFieldType } from "@/types/api";

/**
 * Connection-backed components (the Google Workspace actions and their
 * Microsoft/Slack siblings) select a managed connection through a
 * `connection_ref` input, rendered by the connection picker
 * (`components/core/parameterRenderComponent/components/connectionRefComponent`).
 *
 * The helpers below stay behind `ENABLE_INTEGRATIONS`, which is now a kill
 * switch: a distribution that turns it off keeps these components and their
 * fields out of the palette, the canvas and the Inspector Panel, because
 * without a renderer a required `connection_ref` can never be set and every
 * run of such a component fails.
 */
export const CONNECTION_REF_FIELD_TYPE = "connection_ref";

type MaybeField = Partial<Pick<InputFieldType, "type" | "required">> | null;

export function isConnectionRefField(field: MaybeField | undefined): boolean {
  return field?.type === CONNECTION_REF_FIELD_TYPE;
}

/**
 * True when the component cannot run without a connection. Optional
 * `connection_ref` fields (the legacy Gmail/Drive loaders still accept pasted
 * token JSON) do not count.
 */
export function requiresConnectionRef(
  component: APIClassType | undefined,
): boolean {
  return Object.values(component?.template ?? {}).some(
    (field) =>
      typeof field === "object" &&
      field !== null &&
      isConnectionRefField(field) &&
      field.required === true,
  );
}

/**
 * Returns a copy of the palette data without connection-backed components.
 * Categories are kept (possibly empty) and component payloads are shared, so
 * the store's objects are never mutated.
 */
export function hideConnectionBackedComponents(data: APIDataType): APIDataType {
  return Object.fromEntries(
    Object.entries(data).map(([category, components]) => [
      category,
      Object.fromEntries(
        Object.entries(components).filter(
          ([, component]) => !requiresConnectionRef(component),
        ),
      ),
    ]),
  );
}
