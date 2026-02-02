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
}
