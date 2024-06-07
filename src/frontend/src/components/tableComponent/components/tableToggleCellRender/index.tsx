import { CustomCellRendererProps } from "ag-grid-react";
import { useState } from "react";
import ToggleShadComponent from "../../../toggleShadComponent";

export default function TableToggleCellRender({
  value: { name, enabled, setEnabled },
}: CustomCellRendererProps) {
  const [value, setValue] = useState(enabled);

  return (
    <div className="flex h-full items-center">
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
    </div>
  );
}
