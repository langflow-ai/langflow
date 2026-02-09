export type TAB_TYPES = "Credential" | "Generic";

export type GlobalVariable = {
  id: string;
  type: TAB_TYPES;
  default_fields: string[];
  name: string;
  value?: string;
  category?: string;
  is_valid?: boolean | null;
  validation_error?: string | null;
};
