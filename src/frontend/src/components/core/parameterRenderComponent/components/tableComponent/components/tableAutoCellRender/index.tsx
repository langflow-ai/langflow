import type { CustomCellRendererProps } from "ag-grid-react";
import { uniqueId } from "lodash";
import NumberReader from "@/components/common/numberReader";
import ObjectRender from "@/components/common/objectRender";
import StringReader from "@/components/common/stringReaderComponent";
import DateReader from "@/components/core/dateReaderComponent";
import { Badge } from "@/components/ui/badge";
import { cn, isTimeStampString } from "@/utils/utils";
import ToggleShadComponent from "../../../toggleShadComponent";

interface CustomCellRender extends CustomCellRendererProps {
  formatter?: "json" | "text" | "boolean" | "number" | "undefined" | "null";
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
            setValue={colDef?.onCellValueChanged ? setValue : undefined}
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
      case "undefined":
        return "";
      case "null":
        return "";
      case "boolean":
        value =
          (typeof value === "string" && value.toLowerCase() === "true") ||
          value === true
            ? true
            : false;
        return !!colDef?.onCellValueChanged ||
          !!api.getGridOption("onCellValueChanged") ? (
          <ToggleShadComponent
            value={value}
            handleOnNewValue={(data) => {
              setValue?.(data.value);
            }}
            editNode={true}
            id={"toggle" + colDef?.colId + uniqueId()}
            disabled={false}
          />
        ) : (
          <Badge
            variant={value ? "successStatic" : "errorStatic"}
            size="sq"
            className="h-[18px]"
          >
            {String(value).toLowerCase()}
          </Badge>
        );
      default:
        return String(value);
    }
  }

  return (
    <div className="group flex h-full w-full items-center truncate text-align-last-left">
      {getCellType()}
    </div>
  );
}
