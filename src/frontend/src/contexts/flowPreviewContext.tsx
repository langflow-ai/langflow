import { createContext } from "react";

/**
 * When rendering nodes inside a read-only preview (e.g. FlowHistoryPanel),
 * this context provides the historical edges so that GenericNode sub-components
 * can determine handle visibility from the snapshot rather than from the
 * current draft in the global Zustand store.
 *
 * The context value is `null` by default (normal canvas mode).
 */
export const FlowPreviewEdgesContext = createContext<any[] | null>(null);
