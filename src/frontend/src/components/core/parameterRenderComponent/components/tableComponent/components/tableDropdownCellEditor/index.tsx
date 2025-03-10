import { CustomCellEditorProps } from "ag-grid-react";
import InputComponent from "../../../inputComponent";

export default function TableDropdownCellEditor({
  value,
  values,
  onValueChange,
  colDef,
}: CustomCellEditorProps & { values: string[] }) {
  return (
    <div className="flex h-full items-center px-2">
      <InputComponent
        setSelectedOption={(value) => onValueChange(value)}
        value={value}
        options={values}
        password={false}
        placeholder={"Select an option"}
        id="apply-to-fields"
      />
    </div>
  );
}
