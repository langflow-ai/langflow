export type TAB_TYPES = "Credential" | "Generic";

export type GlobalVariable = {
  id: string;
  type: TAB_TYPES;
  default_fields: string[];
  name: string;
  value?: string;
  category?: string;
};
