import { type ReactNode, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

interface CollapsibleSectionProps {
  id: string;
  title: string;
  /** What the panel holds, shown in the header while it is collapsed. */
  summary: string;
  /** Keeps the panel open, e.g. while it holds an invalid value. */
  forceOpen?: boolean;
  children: ReactNode;
}

export default function CollapsibleSection({
  id,
  title,
  summary,
  forceOpen = false,
  children,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(false);
  const expanded = open || forceOpen;
  const panelId = `${id}-panel`;

  return (
    <div className="flex flex-col gap-3">
      <button
        type="button"
        data-testid={`${id}-toggle`}
        aria-expanded={expanded}
        aria-controls={panelId}
        onClick={() => setOpen(!expanded)}
        className="flex w-full items-center gap-2 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ForwardedIconComponent
          name="ChevronRight"
          aria-hidden="true"
          className={
            expanded
              ? "h-4 w-4 shrink-0 rotate-90 text-muted-foreground transition-transform motion-reduce:transition-none"
              : "h-4 w-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none"
          }
        />
        <span className="shrink-0 text-sm font-medium">{title}</span>
        {!expanded && (
          <span className="min-w-0 truncate text-xs text-muted-foreground">
            {summary}
          </span>
        )}
      </button>
      {expanded && (
        <div id={panelId} className="flex flex-col gap-3 pl-6">
          {children}
        </div>
      )}
    </div>
  );
}
