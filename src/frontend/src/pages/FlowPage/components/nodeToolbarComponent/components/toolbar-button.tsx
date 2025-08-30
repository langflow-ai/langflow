import { memo } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import ShortcutDisplay from "../shortcutDisplay";

export const ToolbarButton = memo(
  ({
    onClick,
    icon,
    label,
    shortcut,
    className,
    dataTestId,
    disabled = false,
    tooltipContent,
  }: {
    onClick: () => void;
    icon: string;
    label?: string;
    shortcut?: any;
    className?: string;
    dataTestId?: string;
    disabled?: boolean;
    tooltipContent?: string | React.ReactNode;
  }) => {
    const content = tooltipContent || <ShortcutDisplay {...shortcut} />;

    if (disabled) {
      // For disabled buttons, wrap in a div to enable tooltip
      return (
        <ShadTooltip content={content} side="top">
          <div className="inline-block cursor-not-allowed">
            <Button
              className={cn("node-toolbar-buttons", className)}
              variant="ghost"
              onClick={onClick}
              size="node-toolbar"
              data-testid={dataTestId}
              disabled={disabled}
            >
              <ForwardedIconComponent name={icon} className="h-4 w-4" />
              {label && <span className="text-mmd font-medium">{label}</span>}
            </Button>
          </div>
        </ShadTooltip>
      );
    }

    return (
      <ShadTooltip content={content} side="top">
        <Button
          className={cn("node-toolbar-buttons", className)}
          variant="ghost"
          onClick={onClick}
          size="node-toolbar"
          data-testid={dataTestId}
          disabled={disabled}
        >
          <ForwardedIconComponent name={icon} className="h-4 w-4" />
          {label && <span className="text-mmd font-medium">{label}</span>}
        </Button>
      </ShadTooltip>
    );
  },
);
