import React from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import {
  DropdownMenuCheckboxItem,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/utils/utils";
import { getModifierKey } from "./utils/canvasUtils";

export type DropdownControlButtonProps = {
  tooltipText?: string;
  onClick?: () => void;
  disabled?: boolean;
  testId?: string;
  label?: string;
  shortcut?: string;
  iconName?: string;
  hasToogle?: boolean;
  toggleValue?: boolean;
  externalLink?: boolean;
};

const DropdownControlButton: React.FC<DropdownControlButtonProps> = ({
  tooltipText,
  onClick = () => {},
  disabled,
  testId,
  label = "",
  shortcut = "",
  iconName,
  hasToogle = false,
  toggleValue = false,
  externalLink = false,
}) => {
  const ariaLabel = tooltipText || label;

  const content = (
    <>
      {iconName && (
        <ForwardedIconComponent
          name={iconName}
          aria-hidden="true"
          className="text-muted-foreground group-hover:text-primary"
        />
      )}
      <div className="flex flex-row items-center justify-between w-full h-full">
        <span className="text-muted-foreground text-sm mr-2 group-hover:text-primary">
          {label}
        </span>
        <div className="flex flex-row items-center text-sm">
          {shortcut && (
            <div
              aria-hidden="true"
              className="flex items-center gap-0.5 text-muted-foreground group-hover:text-primary"
            >
              <span>{getModifierKey()}</span>
              <span>{shortcut}</span>
            </div>
          )}
          {externalLink && (
            <ForwardedIconComponent
              name="external-link"
              aria-hidden="true"
              className="text-muted-foreground group-hover:text-primary opacity-0 group-hover:opacity-100"
            />
          )}
        </div>
      </div>
    </>
  );

  // Menu toggles need their own accessible pattern (role="menuitemcheckbox",
  // a single interactive control) rather than nesting an independently
  // interactive Switch inside a menu item — Radix's CheckboxItem is the
  // purpose-built primitive for exactly this.
  if (hasToogle) {
    return (
      <DropdownMenuCheckboxItem
        data-testid={testId}
        className={cn(
          "group flex items-center justify-center !py-1.5 !px-2 hover:bg-accent h-full rounded-none",
          disabled && "cursor-not-allowed opacity-50",
        )}
        checked={toggleValue}
        onCheckedChange={onClick}
        disabled={disabled}
        title={ariaLabel}
        aria-label={ariaLabel}
        onSelect={(event) => event.preventDefault()}
      >
        {content}
      </DropdownMenuCheckboxItem>
    );
  }

  return (
    <DropdownMenuItem
      data-testid={testId}
      className={cn(
        "group flex items-center justify-center !py-1.5 !px-2 hover:bg-accent h-full rounded-none",
        disabled && "cursor-not-allowed opacity-50",
      )}
      onClick={onClick}
      disabled={disabled}
      title={ariaLabel}
      aria-label={ariaLabel}
    >
      {content}
    </DropdownMenuItem>
  );
};

export default DropdownControlButton;
