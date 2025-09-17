import type { ColDef, GridApi } from "ag-grid-community";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import InputGlobalComponent from "../../../inputGlobalComponent";
import { useGlobalVariableValue } from "../../../inputGlobalComponent/hooks";
import type { GlobalVariable } from "../../../inputGlobalComponent/types";

interface TableGlobalVariableCellProps {
  value: string;
  setValue?: (value: string) => void;
  colDef: ColDef;
  api: GridApi;
  allowCustomValue: boolean;
}

export default function TableGlobalVariableCell({
  value,
  setValue,
  colDef,
  api,
  allowCustomValue,
}: TableGlobalVariableCellProps) {
  const { data: globalVariables } = useGetGlobalVariables();
  const typedGlobalVariables: GlobalVariable[] = globalVariables ?? [];

  // Check if current value is a global variable
  const valueExists = useGlobalVariableValue(value, typedGlobalVariables);

  // Dynamically determine load_from_db based on whether value is a global variable
  const loadFromDb = valueExists && value !== "";

  return (
    <InputGlobalComponent
      id="string-reader-global"
      value={value}
      editNode={false}
      handleOnNewValue={(newValue) => {
        setValue?.(newValue.value);
      }}
      disabled={
        !colDef?.onCellValueChanged && !api.getGridOption("onCellValueChanged")
      }
      load_from_db={loadFromDb}
      allowCustomValue={allowCustomValue}
      password={false}
      display_name=""
      placeholder=""
      isToolMode={false}
      hasRefreshButton={false}
    />
  );
}
