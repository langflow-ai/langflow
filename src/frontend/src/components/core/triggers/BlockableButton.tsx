import { type ReactNode, useId } from "react";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button, type ButtonProps } from "@/components/ui/button";
import { cn } from "@/utils/utils";

export interface BlockableButtonProps extends Omit<ButtonProps, "children"> {
  children?: ReactNode;
  /** Why the action is unavailable, already translated; unset when it is available. */
  blockedReason?: string;
  /** Hover text while the action is available. */
  tooltip?: string;
}

/**
 * A button whose action may be unavailable. Blocked, it stays in the Tab order
 * and explains why, in a tooltip and as its accessible description, instead of
 * going `disabled`, which would skip it and say nothing.
 */
export function BlockableButton({
  blockedReason,
  tooltip,
  onClick,
  className,
  children,
  ...props
}: BlockableButtonProps) {
  const reasonId = useId();
  const blocked = Boolean(blockedReason);
  return (
    <>
      <ShadTooltip content={blockedReason ?? tooltip}>
        <Button
          {...props}
          aria-disabled={blocked || undefined}
          aria-describedby={blocked ? reasonId : undefined}
          className={cn(
            blocked &&
              "cursor-not-allowed opacity-50 aria-disabled:pointer-events-auto",
            className,
          )}
          onClick={(event) => {
            if (!blocked) onClick?.(event);
          }}
        >
          {children}
        </Button>
      </ShadTooltip>
      {/* Outside the button, so the reason is its description, not part of its name. */}
      {blocked && (
        <span id={reasonId} className="sr-only">
          {blockedReason}
        </span>
      )}
    </>
  );
}

export default BlockableButton;
