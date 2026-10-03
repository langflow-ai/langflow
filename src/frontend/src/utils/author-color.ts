/**
 * A color per user, the same everywhere they appear: their avatar in the
 * history timeline and what they changed on a previewed canvas.
 */
const PALETTE = [
  {
    avatar: "bg-accent-blue text-accent-blue-foreground",
    token: "--accent-blue-foreground",
  },
  {
    avatar: "bg-accent-purple-muted text-accent-purple-muted-foreground",
    token: "--accent-purple-muted-foreground",
  },
  {
    avatar: "bg-accent-emerald text-accent-emerald-foreground",
    token: "--accent-emerald-foreground",
  },
  {
    avatar: "bg-accent-amber text-accent-amber-foreground",
    token: "--accent-amber-foreground",
  },
  {
    avatar: "bg-accent-pink text-accent-pink-foreground",
    token: "--accent-pink-foreground",
  },
  {
    avatar: "bg-accent-indigo text-accent-indigo-foreground",
    token: "--accent-indigo-foreground",
  },
];

// FNV-1a: spreads similar ids (UUIDs) across the palette.
function paletteFor(key: string): (typeof PALETTE)[number] {
  let hash = 0x811c9dc5;
  for (const char of key) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 0x01000193);
  }
  return PALETTE[(hash >>> 0) % PALETTE.length];
}

/** Tailwind classes for a user's avatar: a background and its text color. */
export function authorAvatarClasses(key: string): string {
  return paletteFor(key).avatar;
}

/**
 * A user's color as a CSS value, from the same semantic token as their
 * avatar's text, so it follows the theme. `alpha` makes it translucent.
 */
export function authorColor(key: string, alpha?: number): string {
  const token = paletteFor(key).token;
  return alpha === undefined
    ? `hsl(var(${token}))`
    : `hsl(var(${token}) / ${alpha})`;
}
