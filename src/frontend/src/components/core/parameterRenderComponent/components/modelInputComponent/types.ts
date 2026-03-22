export interface ModelOption {
  id?: string;
  name: string;
  icon: string;
  provider: string;
  metadata?: Record<string, unknown>;
}

export type SelectedModel = ModelOption;

export interface ModelInputComponentType {
  options?: ModelOption[];
  placeholder?: string;
  externalOptions?: any;
  /** When true and options are empty, shows "No models enabled" in a clickable dropdown instead of loading state */
  showEmptyState?: boolean;
}
