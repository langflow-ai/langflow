import { useCallback } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import type { NodeDataType } from "@/types/flow";
import { cn } from "@/utils/utils";

interface InspectionPanelEditFieldProps {
  data: NodeDataType;
  name: string;
  title: string;
  description: string;
  isOnCanvas: boolean;
}

export default function InspectionPanelEditField({
  data,
  name,
  title,
  description,
  isOnCanvas,
}: InspectionPanelEditFieldProps) {
  const { handleOnNewValue } = useHandleOnNewValue({
    node: data.node!,
    nodeId: data.id,
    name,
  });

  const handleToggleVisibility = useCallback(() => {
    handleOnNewValue({ advanced: isOnCanvas });
  }, [handleOnNewValue, isOnCanvas]);

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
      <button
        onClick={handleToggleVisibility}
        className={cn(
          "flex h-6 w-6 shrink-0 items-center justify-center rounded-full transition-colors",
          isOnCanvas
            ? "bg-primary/10 text-primary hover:bg-primary/20"
            : "bg-muted text-muted-foreground hover:bg-muted-foreground/20 hover:text-foreground",
        )}
        data-testid={`show${name}`}
        id={`show${name}`}
        aria-checked={isOnCanvas}
        role="checkbox"
      >
        <IconComponent
          name={isOnCanvas ? "Minus" : "Plus"}
          className="h-3.5 w-3.5"
        />
      </button>
    </div>
  );
}
