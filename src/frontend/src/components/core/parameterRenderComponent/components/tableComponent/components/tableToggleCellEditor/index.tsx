import { CustomCellEditorProps } from "ag-grid-react";
import { uniqueId } from "lodash";
import ToggleShadComponent from "../../../toggleShadComponent";

export default function TableToggleCellEditor({
  value,
  onValueChange,
  colDef,
}: CustomCellEditorProps) {
  value =
    (typeof value === "string" && value.toLowerCase() === "true") ||
    value === true
      ? true
      : false;
  return (
    <div className="flex h-full items-center px-2">
      <ToggleShadComponent
        value={value}
        handleOnNewValue={(data) => {
          onValueChange?.(data.value);
        }}
        editNode={true}
        id={"toggle" + colDef?.colId + uniqueId()}
        disabled={false}
      />
    </div>
  );
}
