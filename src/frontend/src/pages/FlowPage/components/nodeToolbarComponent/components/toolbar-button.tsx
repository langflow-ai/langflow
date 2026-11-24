import { memo } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import ShortcutDisplay from "../shortcutDisplay";

type ToolbarShortcut = {
  display_name?: string;
  name?: string;
  shortcut: string;
  sidebar?: boolean;
};

export const ToolbarButton = memo(
  ({
    onClick,
    icon,
    label,
    shortcut,
    className,
    dataTestId,
    isActive,
  }: {
    onClick: () => void;
    icon: string;
    label?: string;
    shortcut?: ToolbarShortcut;
    className?: string;
    dataTestId?: string;
    isActive?: boolean;
  }) => (
    <ShadTooltip
      content={shortcut ? <ShortcutDisplay {...shortcut} /> : (label ?? icon)}
      side="top"
      avoidCollisions={true}
      ariaDescribedBy={undefined}
    >
      <Button
        className={cn(
          "node-toolbar-buttons",
          // Pressed-toggle affordance (matches the repo's active-toggle
          // pattern) so open/closed states read clearly at a glance.
          isActive && "bg-muted text-foreground",
          className,
        )}
        variant="ghost"
        onClick={onClick}
        size="node-toolbar"
        data-testid={dataTestId}
        aria-label={label ?? shortcut?.name ?? icon}
        aria-pressed={isActive}
      >
        <ForwardedIconComponent name={icon} className="h-4 w-4" />
        {label && <span className="text-mmd font-medium">{label}</span>}
      </Button>
    </ShadTooltip>
  ),
);
