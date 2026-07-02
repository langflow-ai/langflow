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
  }: {
    onClick: () => void;
    icon: string;
    label?: string;
    shortcut?: ToolbarShortcut;
    className?: string;
    dataTestId?: string;
  }) => (
    <ShadTooltip
      content={shortcut ? <ShortcutDisplay {...shortcut} /> : (label ?? icon)}
      side="top"
      avoidCollisions={true}
    >
      <Button
        className={cn("node-toolbar-buttons", className)}
        variant="ghost"
        onClick={onClick}
        size="node-toolbar"
        data-testid={dataTestId}
        aria-label={label ?? shortcut?.name ?? icon}
      >
        <ForwardedIconComponent name={icon} className="h-4 w-4" />
        {label && <span className="text-mmd font-medium">{label}</span>}
      </Button>
    </ShadTooltip>
  ),
);
