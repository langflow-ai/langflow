import { authorAvatarClasses } from "@/utils/author-color";
import { cn } from "@/utils/utils";

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
        name ? authorAvatarClasses(id) : "bg-muted text-muted-foreground",
        className,
      )}
    >
      {(name ?? "?").charAt(0)}
    </span>
  );
}
