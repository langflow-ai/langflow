import React from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import ToggleShadComponent from "../parameterRenderComponent/components/toggleShadComponent";
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
}) => (
  <Button
    data-testid={testId}
    className={cn(
      "group flex items-center justify-center !py-1.5 !px-2 hover:bg-accent h-full rounded-none",
      disabled && "cursor-not-allowed opacity-50",
    )}
    onClick={onClick}
    variant="ghost"
    disabled={disabled}
    title={tooltipText || ""}
  >
    {iconName && (
      <ForwardedIconComponent
        name={iconName}
        className="text-muted-foreground group-hover:text-primary"
      />
    )}
    <div className="flex flex-row items-center justify-between w-full h-full">
      <span className="text-muted-foreground text-sm mr-2 group-hover:text-primary">
        {label}
      </span>
      <div
        className={cn(
          "flex flex-row items-center text-sm",
          shortcut && "w-[25px]",
        )}
      >
        {shortcut && (
          <div className="flex items-center justify-between w-full text-muted-foreground group-hover:text-primary">
            <span>{getModifierKey()}</span>
            <span className="">{shortcut}</span>
          </div>
        )}
        {externalLink && (
          <ForwardedIconComponent
            name="external-link"
            className="text-muted-foreground group-hover:text-primary opacity-0 group-hover:opacity-100"
          />
        )}
      </div>
    </div>
    {hasToogle && (
      <ToggleShadComponent
        value={toggleValue}
        handleOnNewValue={onClick}
        editNode={true}
        id="helper_lines"
        disabled={false}
      />
    )}
  </Button>
);

export default DropdownControlButton;
