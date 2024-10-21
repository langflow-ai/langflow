import RenderIcons from "@/components/renderIconComponent";
import { cn } from "@/utils/utils";

export default function ShortcutDisplay({
  name,
  shortcut,
}: {
  name?: string;
  shortcut: string;
}): JSX.Element {
  const fixedShortcut = shortcut?.split("+");
  return (
    <div className="flex justify-center">
      {name && <span> {name} </span>}
      <span
        className={cn(
          "flex items-center rounded-sm bg-muted px-1.5 py-[0.1em] text-lg text-muted-foreground",
          name && "ml-3",
        )}
      >
        <RenderIcons filteredShortcut={fixedShortcut} />
      </span>
    </div>
  );
}
