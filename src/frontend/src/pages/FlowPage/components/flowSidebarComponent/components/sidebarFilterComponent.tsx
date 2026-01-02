import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";

export function SidebarFilterComponent({
  name,
  description,
  resetFilters,
}: {
  name: string;
  description: string;
  resetFilters: () => void;
}) {
  const tooltips = description.split("\n");
  const plural = tooltips.length > 1 ? "s" : "";
  return (
    <div
      className={`mb-0.5 flex w-full items-center overflow-hidden justify-between rounded border p-2 text-sm text-foreground`}
    >
      <div className="flex flex-1 items-center gap-1.5 overflow-hidden">
        <ForwardedIconComponent
          name="ListFilter"
          className={`h-4 w-4 shrink-0 stroke-2`}
        />
        <div className="flex flex-1 overflow-hidden">
          {name}
          {plural}:{" "}
          <div className="flex-1 overflow-hidden truncate pl-1">
            {tooltips.join(", ")}
          </div>
        </div>
      </div>
      <ShadTooltip
        side="right"
        styleClasses="max-w-full"
        content="Remove filter"
      >
        <Button
          unstyled
          className="shrink-0"
          onClick={resetFilters}
          data-testid="sidebar-filter-reset"
        >
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
