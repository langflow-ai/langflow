/** Distance from the node top edge to the selection chrome row (matches legacy `-top-12`). */
export const NODE_SELECTION_CHROME_TOP_CLASS = "-top-12";

/** Shared flex row: avatars (start) · toolbar (center) · actions (end). */
export const NODE_SELECTION_CHROME_ROW_CLASS =
  "pointer-events-none absolute inset-x-0 flex items-center gap-2 overflow-visible";

/** Keeps the collaboration bump above the centered toolbar when it expands on hover. */
export const NODE_SELECTION_CHROME_BUMP_SLOT_CLASS =
  "pointer-events-auto relative z-[60] flex min-w-8 flex-1 items-center justify-start overflow-visible";

export const NODE_SELECTION_CHROME_TOOLBAR_SLOT_CLASS =
  "pointer-events-auto relative z-40 shrink-0";
