import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";

/** An (i) button next to a label: the hint opens on hover, keyboard focus, or a tap. */
export default function InfoHint({
  hint,
  label,
  testId,
}: {
  hint: string;
  /** The button's accessible name, e.g. "About Off topic". */
  label: string;
  testId?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <ShadTooltip
      content={hint}
      delayDuration={200}
      open={open}
      setOpen={setOpen}
    >
      <button
        type="button"
        aria-label={label}
        data-testid={testId}
        // Touch screens have no hover: a tap toggles the hint.
        onClick={() => setOpen(!open)}
        onBlur={() => setOpen(false)}
        className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ForwardedIconComponent
          name="Info"
          aria-hidden="true"
          className="h-3.5 w-3.5"
        />
      </button>
    </ShadTooltip>
  );
}
