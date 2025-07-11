import RenderIcons from "@/components/common/renderIconComponent";
import { cn } from "@/utils/utils";

export default function ShortcutDisplay({
  display_name,
  shortcut,
  sidebar = false,
}: {
  display_name?: string;
  shortcut: string;
  sidebar?: boolean;
}): JSX.Element {
  const fixedShortcut = shortcut?.split("+");
  return (
    <>
      {sidebar ? (
        <div className="flex justify-center">
          {display_name && <span> {display_name} </span>}
          <span
            className={cn(
              "bg-muted text-muted-foreground flex h-4 w-4 items-center justify-center rounded-sm",
              display_name && "ml-3",
            )}
          >
            <RenderIcons filteredShortcut={fixedShortcut} />
          </span>
        </div>
      ) : (
        <div className="flex content-center items-center justify-center self-center text-xs">
          <span> {display_name} </span>
          <span
            className={`bg-primary-hover text-muted ml-3 flex items-center rounded-sm px-1.5 py-[0.1em]`}
          >
            <RenderIcons filteredShortcut={fixedShortcut} />
          </span>
        </div>
      )}
    </>
  );
}
