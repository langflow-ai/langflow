import type { ProviderScopeParams } from "@/controllers/API/helpers/provider-scope";
import type { APIClassType } from "@/types/api";

export interface ModelOption {
  id?: string;
  name: string;
  icon: string;
  provider: string;
  metadata?: Record<string, unknown>;
}

export type ExternalOptionsType = {
  fields: { data: { node: APIClassType } };
  functionality?: string;
};

export type SelectedModel = ModelOption;

export interface ModelInputComponentType {
  options?: ModelOption[];
  placeholder?: string;
  externalOptions?: ExternalOptionsType;
  /** When true and options are empty, shows "No models enabled" in a clickable dropdown instead of loading state */
  showEmptyState?: boolean;
  /** Explicitly set the model type filter ("llm" or "embeddings"). Overrides the nodeClass-derived default. */
  modelType?: "llm" | "embeddings";
  /**
   * Explicit policy scope for non-canvas pickers. An empty object deliberately
   * requests the install-wide policy; omission keeps canvas pickers inert until
   * the current flow has been persisted.
   */
  providerScope?: ProviderScopeParams;
  /** Accessible name for the combobox trigger (WCAG 4.1.2). */
  "aria-label"?: string;
  /** Id of the error text describing this field (aria-describedby, WCAG 3.3.1). */
  ariaDescribedBy?: string;
  /** Marks the combobox trigger invalid when the field failed validation. */
  ariaInvalid?: boolean;
}
