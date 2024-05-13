import { CustomCellRendererProps } from "ag-grid-react";
import { isTimeStampString } from "../../utils/utils";
import { isArray } from "lodash";

export default function TableAutoCellRender({
  value,
}: CustomCellRendererProps) {
  //empty field case
  if (value === undefined || value === null) {
    return undefined;
  }
  if (typeof value === "string") {
    //use default renderer
    if (isTimeStampString(value)) {
      const date = new Date(value);
      const formattedDate = date.toLocaleString("en-US", {
        day: "numeric",
        month: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "numeric",
        second: "numeric",
      });
      return formattedDate;
    }
    return value;
  }
  if (typeof value === "number") {
    return value.toString();
  }
  if (typeof value === "object" && isArray(value)) {
    if (value.length === 0) {
      return "[]";
    }
    return JSON.stringify(value);
  }
  if (typeof value === "object") {
    if (value.definitions) {
      // use a custom render defined by the sender
    }
    //use custom renderer for object
    return <div>{JSON.stringify(value)}</div>;
  }
}
