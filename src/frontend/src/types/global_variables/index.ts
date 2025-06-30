export type GlobalVariable = {
  id: string;
  type: string;
  default_fields: string[];
  name: string;
  value?: string;
  category?: string | null;
};
