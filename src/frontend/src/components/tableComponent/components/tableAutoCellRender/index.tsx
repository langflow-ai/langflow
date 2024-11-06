import { CustomCellRendererProps } from "ag-grid-react";
import { cn, isTimeStampString } from "../../../../utils/utils";
import DateReader from "../../../dateReaderComponent";
import NumberReader from "../../../numberReader";
import ObjectRender from "../../../objectRender";
import StringReader from "../../../stringReaderComponent";
import { Badge } from "../../../ui/badge";

interface CustomCellRender extends CustomCellRendererProps {
  formatter?: "json" | "text";
}

export default function TableAutoCellRender({
  value,
  setValue,
  colDef,
  formatter,
  api,
}: CustomCellRender) {
  function getCellType() {
    let format: string = formatter ? formatter : typeof value;
    //convert text to string to bind to the string reader
    format = format === "text" ? "string" : format;
    format = format === "json" ? "object" : format;

    switch (format) {
      case "object":
        return (
          <ObjectRender
            setValue={!!colDef?.onCellValueChanged ? setValue : undefined}
            object={value}
          />
        );

      case "string":
        if (isTimeStampString(value)) {
          return <DateReader date={value} />;
        }
        //TODO: REFACTOR FOR ANY LABEL NOT HARDCODED
        else if (value === "success") {
          return (
            <Badge
              variant="successStatic"
              size="sq"
              className={cn("h-[18px] w-full justify-center")}
            >
              {value}
            </Badge>
          );
        } else if (value === "failure") {
          return (
            <Badge
              variant="errorStatic"
              size="sq"
              className={cn("h-[18px] w-full justify-center")}
            >
              {value}
            </Badge>
          );
        } else {
          return (
            <StringReader
              editable={
                !!colDef?.onCellValueChanged ||
                !!api.getGridOption("onCellValueChanged")
              }
              setValue={setValue!}
              string={value}
            />
          );
        }
      case "number":
        return <NumberReader number={value} />;
      default:
        return String(value);
    }
  }

  return (
    <div className="group flex h-full w-full truncate text-align-last-left">
      {getCellType()}
    </div>
  );
}
