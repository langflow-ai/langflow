import ForwardedIconComponent from "@/components/genericIconComponent";
import ShadTooltip from "@/components/shadTooltipComponent";
import { Button } from "@/components/ui/button";

export function SidebarFilterComponent({
  isInput,
  type,
  resetFilters,
}: {
  isInput: boolean;
  type: string;
  resetFilters: () => void;
}) {
  return (
    <div className="mb-0.5 flex w-full items-center justify-between rounded border bg-muted p-1 px-2 text-xs font-medium text-primary">
      <div className="flex flex-1 items-center gap-1.5">
        <ForwardedIconComponent
          name="ListFilter"
          className="h-4 w-4 shrink-0 stroke-2"
        />
        <div className="flex-1 overflow-hidden truncate">
          {isInput ? "Input" : "Output"}: {type}
        </div>
      </div>
      <ShadTooltip
        side="right"
        styleClasses="max-w-full"
        content="Remove filter"
      >
        <Button unstyled className="shrink-0" onClick={resetFilters}>
          <ForwardedIconComponent
            name="X"
            className="h-4 w-4 stroke-2"
            aria-hidden="true"
          />
        </Button>
      </ShadTooltip>
    </div>
  );
}
