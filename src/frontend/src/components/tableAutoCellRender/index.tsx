import { CustomCellRendererProps } from "ag-grid-react";
import { cn, isTimeStampString } from "../../utils/utils";
import ArrayReader from "../arrayReaderComponent";
import DateReader from "../dateReaderComponent";
import NumberReader from "../numberReader";
import ObjectRender from "../objectRender";
import StringReader from "../stringReaderComponent";
import { Label } from "../ui/label";
import { Badge } from "../ui/badge";

export default function TableAutoCellRender({
  value,
}: CustomCellRendererProps) {
  function getCellType() {
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
        }
        //TODO: REFACTOR FOR ANY LABEL NOT HARDCODED
        else if (value === "success") {
          return (
            <Badge
              variant="outline"
              size="sq"
              className={cn(
                "min-w-min bg-success-background text-success-foreground hover:bg-success-background",
              )}
            >
              {value}
            </Badge>
          );
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

  return (
    <div className="group flex h-full w-full items-center align-middle">
      {getCellType()}
    </div>
  );
}
