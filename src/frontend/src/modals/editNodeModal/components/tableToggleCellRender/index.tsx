import { CustomCellRendererProps } from "ag-grid-react";
import { useState } from "react";
import ToggleShadComponent from "../../../../components/toggleShadComponent";

export default function TableToggleCellRender({
  value: { name, enabled, setEnabled },
}: CustomCellRendererProps) {
  const [value, setValue] = useState(enabled);

  return (
    <ToggleShadComponent
      id={"show" + name}
      enabled={value}
      setEnabled={(e) => {
        setValue(e);
        setEnabled(e);
      }}
      size="small"
      editNode={true}
    />
  );
}
