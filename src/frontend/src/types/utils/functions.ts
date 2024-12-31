import { FieldParserType, FieldValidatorType } from "../api";

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
}

export interface ColumnField {
  name: string;
  display_name: string;
  sortable: boolean;
  filterable: boolean;
  formatter?: FormatterType;
  description?: string;
  disable_edit?: boolean;
  default?: any; // Add this line
  edit_mode?: "modal" | "inline";
}
