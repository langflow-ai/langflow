import { CustomCellRendererProps } from "ag-grid-react";
import { isTimeStampString } from "../../utils/utils";
import ArrayReader from "../arrayReaderComponent";
import DateReader from "../dateReaderComponent";
import NumberReader from "../numberReader";
import ObjectRender from "../objectRender";
import StringReader from "../stringReaderComponent";

export default function TableAutoCellRender({
  value,
}: CustomCellRendererProps) {
  switch (typeof value) {
    case "object":
      if (value === null) {
        return String(value);
      } else if (Array.isArray(value)) {
        return <ArrayReader array={value} />;
      } else if (value.definitions) {
        // use a custom render defined by the sender
      } else {
        return <ObjectRender object={value} />;
      }
      break;
    case "string":
      if (isTimeStampString(value)) {
        return <DateReader date={value} />;
      } else {
        return <StringReader string={value} />;
      }
      break;
    case "number":
      return <NumberReader number={value} />;
    default:
      return String(value);
  }
}
