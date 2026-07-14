import type { ReactNode } from "react";

/** Eyebrow + body wrapper for a section inside a tool-call card.
 * Used to label Arguments, Output, and Error sections so the reader can
 * tell at a glance which part of the tool call they're looking at — the
 * surrounding accordion only signals "this is a tool call", not where
 * the boundary between input and result sits. The eyebrow style is
 * intentionally quiet (small-caps muted text) so it scaffolds the
 * sections without competing with the actual content. */
export function ToolSection({
  eyebrow,
  children,
}: {
  eyebrow: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-[10px] uppercase tracking-wider font-medium text-muted-foreground">
        {eyebrow}
      </div>
      {children}
    </div>
  );
}
