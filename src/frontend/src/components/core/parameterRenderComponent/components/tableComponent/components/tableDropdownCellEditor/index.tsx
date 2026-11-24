import type { CustomCellEditorProps } from "ag-grid-react";
import { useTranslation } from "react-i18next";
import InputComponent from "../../../inputComponent";

export default function TableDropdownCellEditor({
  value,
  values,
  onValueChange,
  colDef,
  eGridCell,
}: CustomCellEditorProps & { values: string[] }) {
  const { t } = useTranslation();
  return (
    <div
      style={{ width: eGridCell.clientWidth }}
      className="flex h-full items-center px-2"
    >
      <InputComponent
        setSelectedOption={(value) => onValueChange(value)}
        value={value}
        options={values}
        password={false}
        placeholder={t("component.selectOption")}
        id="apply-to-fields"
      />
    </div>
  );
}
