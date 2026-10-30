import { cn } from "@/utils/utils";

// The number carries the identity; the color only helps the eye match a version across screens.
const MARKER_COLORS = [
  "bg-accent-blue-foreground",
  "bg-accent-amber-foreground",
  "bg-accent-emerald-foreground",
  "bg-accent-pink-foreground",
  "bg-accent-indigo-foreground",
];

/** A model version's number in a comparison, in its color; decorative next to a text label. */
export default function VariantMarker({
  index,
  className,
}: {
  index: number;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-semibold tabular-nums text-background",
        MARKER_COLORS[index % MARKER_COLORS.length],
        className,
      )}
    >
      {index + 1}
    </span>
  );
}
