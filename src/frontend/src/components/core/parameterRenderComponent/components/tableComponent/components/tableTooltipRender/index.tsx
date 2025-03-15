import { CustomTooltipProps } from "ag-grid-react";

export default function TableTooltipRender({ value }: CustomTooltipProps) {
  return (
    <div className="bg-popover text-popover-foreground animate-in fade-in-50 data-[side=bottom]:slide-in-from-top-1 data-[side=left]:slide-in-from-right-1 data-[side=right]:slide-in-from-left-1 data-[side=top]:slide-in-from-bottom-1 z-45 overflow-y-auto rounded-md border px-3 py-1.5 text-sm shadow-md">
      {value}
    </div>
  );
}
