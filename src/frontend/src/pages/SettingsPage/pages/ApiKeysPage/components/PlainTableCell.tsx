import type { CustomCellRendererProps } from "ag-grid-react";

/** Read-only cell text; avoids StringReader/TextModal so row values are not mistaken for editable/view-in-modal fields. */
export function PlainTableCell({ value }: CustomCellRendererProps) {
  const display = value == null ? "" : String(value);
  return (
    <div className="flex h-full w-full items-center truncate text-left">
      {/* Invisible char matches StringReader when empty (AG Grid cell layout quirk). */}
      <span className="truncate">{display || "\u200e"}</span>
    </div>
  );
}
