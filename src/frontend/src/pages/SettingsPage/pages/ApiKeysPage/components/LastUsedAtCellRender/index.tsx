import type { CustomCellRendererProps } from "ag-grid-react";
import DateReader from "@/components/core/dateReaderComponent";

export default function LastUsedAtCellRender({
  value,
}: CustomCellRendererProps) {
  if (value && typeof value === "string" && value.includes("T")) {
    return (
      <div className="flex h-full w-full items-center truncate">
        <DateReader date={value} />
      </div>
    );
  }

  return (
    <div className="flex h-full w-full items-center text-muted-foreground">
      {value ? value : "Never"}
    </div>
  );
}
