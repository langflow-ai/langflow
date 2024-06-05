import { CustomCellRendererProps } from "ag-grid-react";

export default function TableMultilineCellRender({
  value,
}: CustomCellRendererProps) {
  return (
    <span className="text-wrap py-2.5 leading-5 truncate-multiline">
      {value}
    </span>
  );
}
