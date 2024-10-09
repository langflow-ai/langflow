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
  default?: any; // Add this line
}
