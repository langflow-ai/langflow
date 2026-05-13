/**
 * Shared Tailwind class strings for the assistant panel's ghost-style action
 * buttons. Keeps the plan / flow-proposal / component-result / file-card cards
 * visually consistent: changing a dimension or hover colour here updates every
 * card at once, instead of drifting across 4 copies of the same string.
 *
 *  - GHOST_PRIMARY_BUTTON   — the affirmative action on a card. Examples:
 *    Continue (plan), Add to canvas (flow), Approve (component).
 *  - GHOST_SECONDARY_BUTTON — neutral/destructive secondary actions. Examples:
 *    Dismiss, Reset, Replace canvas, View Code, Open, Download.
 */

export const GHOST_PRIMARY_BUTTON =
  "flex h-7 items-center gap-1.5 rounded-md px-2 text-sm font-medium text-accent-emerald-foreground transition-colors hover:bg-accent-emerald-foreground/10";

export const GHOST_SECONDARY_BUTTON =
  "flex h-7 items-center gap-1.5 rounded-md px-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground";
