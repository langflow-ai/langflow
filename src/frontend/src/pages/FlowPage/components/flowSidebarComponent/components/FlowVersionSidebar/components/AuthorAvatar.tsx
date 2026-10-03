import { cn } from "@/utils/utils";

const COLORS = [
  "bg-accent-blue text-accent-blue-foreground",
  "bg-accent-purple-muted text-accent-purple-muted-foreground",
  "bg-accent-emerald text-accent-emerald-foreground",
  "bg-accent-amber text-accent-amber-foreground",
  "bg-accent-pink text-accent-pink-foreground",
  "bg-accent-indigo text-accent-indigo-foreground",
];

// FNV-1a: spreads similar ids (UUIDs) across the palette.
function colorFor(key: string): string {
  let hash = 0x811c9dc5;
  for (const char of key) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 0x01000193);
  }
  return COLORS[(hash >>> 0) % COLORS.length];
}

interface AuthorAvatarProps {
  /** Stable key for the color, such as the user id. */
  id: string;
  name: string | null;
  className?: string;
}

/** A user's initial on a color that stays the same everywhere they appear. */
export default function AuthorAvatar({
  id,
  name,
  className,
}: AuthorAvatarProps) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex h-6 w-6 shrink-0 select-none items-center justify-center rounded-full text-[11px] font-semibold uppercase ring-2 ring-background",
        name ? colorFor(id) : "bg-muted text-muted-foreground",
        className,
      )}
    >
      {(name ?? "?").charAt(0)}
    </span>
  );
}
