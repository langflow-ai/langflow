export type ExtensionEventType =
  | "bundle_reloaded"
  | "components_added"
  | "components_removed"
  | "flow_migrated"
  | "extension_error"
  | "bundle_reload_failed";

export type ExtensionEvent = {
  type: ExtensionEventType;
  timestamp: number;
  payload: Record<string, unknown>;
};

export type ExtensionEventsResponse = {
  events: ExtensionEvent[];
  settled: boolean;
};
