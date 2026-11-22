import { type FocusEvent, type ReactNode, useState } from "react";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { cn } from "@/utils/utils";

/** Explains a mark on hover or keyboard focus; the trigger is focusable so the hint is not mouse-only. */
export default function HintTooltip({
  hint,
  children,
  underline = false,
}: {
  hint: string;
  children: ReactNode;
  /** A dotted underline tells plain text apart from text that explains itself. */
  underline?: boolean;
}) {
  const [open, setOpen] = useState(false);
  // Focusing a trigger at the viewport edge scrolls it into view, and a tooltip closes on any scroll:
  // open again once that scroll has happened, or keyboard users would never see the hint.
  const openAfterFocusScroll = (event: FocusEvent<HTMLButtonElement>) => {
    const trigger = event.currentTarget;
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        // A quick Tab may already have moved on.
        if (document.activeElement === trigger) setOpen(true);
      }),
    );
  };

  return (
    <ShadTooltip
      content={hint}
      delayDuration={200}
      open={open}
      setOpen={setOpen}
    >
      {/* A button, not a focusable span: a tabbable element needs a widget role. A tap toggles the hint. */}
      <button
        type="button"
        onFocus={openAfterFocusScroll}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen(!open)}
        className={cn(
          "cursor-help rounded-sm bg-transparent p-0 text-inherit [font:inherit] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          underline && "underline decoration-dotted underline-offset-4",
        )}
      >
        {children}
      </button>
    </ShadTooltip>
  );
}
