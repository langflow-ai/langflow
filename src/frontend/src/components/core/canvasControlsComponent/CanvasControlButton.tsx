import { ControlButton } from "@xyflow/react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { cn } from "@/utils/utils";

type CanvasControlButtonProps = {
  iconName: string;
  tooltipText: string;
  onClick: () => void;
  disabled?: boolean;
  backgroundClasses?: string;
  iconClasses?: string;
  testId?: string;
  navItemId?: string;
};

export const CanvasControlButton = ({
  iconName,
  tooltipText,
  onClick,
  disabled,
  backgroundClasses,
  iconClasses,
  testId,
  navItemId,
}: CanvasControlButtonProps): JSX.Element => {
  return (
    <ControlButton
      data-testid={testId}
      data-sidebar-collapsed-nav-item={navItemId}
      className="group !h-8 !w-8 rounded !p-0 focus-visible:!outline focus-visible:!outline-2 focus-visible:!outline-offset-2 focus-visible:!outline-current"
      onClick={onClick}
      disabled={disabled}
      aria-label={tooltipText}
    >
      <ShadTooltip content={tooltipText} side="right">
        <div
          className={cn(
            "rounded p-2.5 text-muted-foreground group-hover:text-primary",
            backgroundClasses,
          )}
        >
          <ForwardedIconComponent
            name={iconName}
            aria-hidden="true"
            className={cn("scale-150 h-8 w-8", iconClasses)}
          />
        </div>
      </ShadTooltip>
    </ControlButton>
  );
};

export default CanvasControlButton;
