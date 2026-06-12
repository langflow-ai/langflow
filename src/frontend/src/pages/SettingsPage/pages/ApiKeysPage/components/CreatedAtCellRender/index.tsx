import type { CustomCellRendererProps } from "ag-grid-react";
import DateReader from "@/components/core/dateReaderComponent";

export default function CreatedAtCellRender({
  value,
}: CustomCellRendererProps) {
  if (value && typeof value === "string" && value.includes("T")) {
    return (
      <div className="flex h-full w-full items-center truncate">
        <DateReader date={value} />
      </div>
    );
  }

  return <div className="flex h-full w-full items-center">—</div>;
}
