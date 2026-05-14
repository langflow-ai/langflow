/**
 * Shared Tailwind class strings for the assistant panel's action buttons.
 * Keeps cards visually consistent: changing a dimension or hover colour here
 * updates every card at once, instead of drifting across copies of the
 * same string.
 *
 *  - GHOST_PRIMARY_BUTTON   — the affirmative action on a card. Examples:
 *    Continue (plan), Add to canvas (flow), Approve (component).
 *  - GHOST_SECONDARY_BUTTON — neutral/destructive secondary actions. Examples:
 *    Dismiss, Reset, Replace canvas, View Code, Open, Download.
 *  - SOLID_PRIMARY_BUTTON   — affirmative action on per-field decision cards
 *    where each card needs more visual weight than ghost (Accept on a
 *    propose_field_edit row). Maps to ``bg-primary`` / ``text-primary-foreground``
 *    so the button auto-inverts between light and dark themes.
 *  - SOLID_SECONDARY_BUTTON — destructive counterpart of SOLID_PRIMARY_BUTTON
 *    (Dismiss on a propose_field_edit row). Uses ``bg-secondary-foreground``
 *    so the contrast against the lighter card surface stays high.
 */

export const GHOST_PRIMARY_BUTTON =
  "flex h-7 items-center gap-1.5 rounded-md px-2 text-sm font-medium text-accent-emerald-foreground transition-colors hover:bg-accent-emerald-foreground/10";

export const GHOST_SECONDARY_BUTTON =
  "flex h-7 items-center gap-1.5 rounded-md px-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground";

export const SOLID_PRIMARY_BUTTON =
  "flex h-7 items-center gap-1 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90";

export const SOLID_SECONDARY_BUTTON =
  "flex h-7 items-center gap-1 rounded-md bg-secondary-foreground px-3 text-xs font-medium text-secondary transition-colors hover:bg-secondary-foreground/90";
