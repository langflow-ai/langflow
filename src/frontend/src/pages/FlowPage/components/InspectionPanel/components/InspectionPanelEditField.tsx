import { useCallback } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import type { NodeDataType } from "@/types/flow";
import { cn } from "@/utils/utils";

interface InspectionPanelEditFieldProps {
  data: NodeDataType;
  name: string;
  title: string;
  description: string;
  isOnCanvas: boolean;
  isExposedToApi: boolean;
}

export default function InspectionPanelEditField({
  data,
  name,
  title,
  description,
  isOnCanvas,
  isExposedToApi,
}: InspectionPanelEditFieldProps) {
  const { handleOnNewValue } = useHandleOnNewValue({
    node: data.node!,
    nodeId: data.id,
    name,
  });

  const handleToggleVisibility = useCallback(() => {
    handleOnNewValue({ advanced: isOnCanvas });
  }, [handleOnNewValue, isOnCanvas]);

  const handleToggleApiExposure = useCallback(() => {
    handleOnNewValue({ api_only: !isExposedToApi });
  }, [handleOnNewValue, isExposedToApi]);

  return (
    <div
      className={cn(
        "group flex items-center justify-between gap-3 rounded-md px-3 py-2",
        "hover:bg-muted/50",
      )}
    >
      <div className="flex flex-col gap-0.5 overflow-hidden">
        <span className="truncate text-sm font-medium">{title}</span>
        {description && (
          <span className="truncate text-xs text-muted-foreground">
            {description}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <ShadTooltip
          content={isOnCanvas ? "Hide from node" : "Show on node"}
          side="top"
        >
          <button
            onClick={handleToggleVisibility}
            className={cn(
              "flex h-6 w-6 shrink-0 items-center justify-center rounded-full transition-colors",
              isOnCanvas
                ? "bg-primary/10 text-primary hover:bg-primary/20"
                : "bg-muted text-muted-foreground hover:bg-muted-foreground/20 hover:text-foreground",
            )}
            data-testid={`toggle-${name}`}
          >
            <IconComponent
              name={isOnCanvas ? "Minus" : "Plus"}
              className="h-3.5 w-3.5"
            />
          </button>
        </ShadTooltip>
        <ShadTooltip
          content={isExposedToApi ? "Remove from API schema" : "Expose in API schema"}
          side="top"
        >
          <button
            onClick={handleToggleApiExposure}
            className={cn(
              "flex h-4 w-4 shrink-0 items-center justify-center transition-colors",
              isExposedToApi
                ? "text-primary"
                : "text-muted-foreground/50 hover:text-muted-foreground",
            )}
            data-testid={`toggle-api-${name}`}
          >
            <IconComponent name="Plug" className="h-3.5 w-3.5" />
          </button>
        </ShadTooltip>
      </div>
    </div>
  );
}
