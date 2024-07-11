export type getCodesObjProps = {
  runCurlCode: string;
  webhookCurlCode: string;
  pythonApiCode: string;
  jsApiCode: string;
  pythonCode: string;
  widgetCode: string;
};

export type getCodesObjReturn = Array<{ name: string; code: string }>;

enum FormatterType {
  date = "date",
  text = "text",
  number = "number",
  currency = "currency",
  json = "json",
}

export type ColumnField = {
  display_name: string;
  name: string;
  sortable: boolean;
  filterable: boolean;
  formatter?: FormatterType;
};
