export type getCodesObjProps = {
  runCurlCode: string;
  webhookCurlCode: string;
  pythonApiCode: string;
  jsApiCode: string;
  pythonCode: string;
  widgetCode: string;
};

export type getCodesObjReturn = Array<{ name: string; code: string }>;

export enum FormatterType {
  date = "date",
  text = "text",
  number = "number",
  json = "json",
  boolean = "boolean",
}

export interface ColumnField {
  name: string;
  display_name: string;
  sortable: boolean;
  filterable: boolean;
  formatter?: FormatterType;
  // Declared backend type (e.g. "str", "boolean"); the formatter is derived from it when absent.
  type?: string;
  description?: string;
  load_from_db?: boolean;
  disable_edit?: boolean;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  default?: any;
  edit_mode?: "modal" | "inline" | "popover";
  hidden?: boolean;
  options?: string[];
}
