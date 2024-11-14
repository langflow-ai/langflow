import RenderIcons from "@/components/renderIconComponent";
import { cn } from "@/utils/utils";

export default function ShortcutDisplay({
  name,
  shortcut,
  sidebar = false,
}: {
  name?: string;
  shortcut: string;
  sidebar?: boolean;
}): JSX.Element {
  const fixedShortcut = shortcut?.split("+");
  return (
    <>
      {sidebar ? (
        <div className="flex justify-center">
          {name && <span> {name} </span>}
          <span
            className={cn(
              "flex h-[16px] w-[16px] items-center justify-center rounded-sm bg-muted text-muted-foreground",
              name && "ml-3",
            )}
          >
            <RenderIcons filteredShortcut={fixedShortcut} />
          </span>
        </div>
      ) : (
        <div className="flex content-center items-center justify-center self-center text-[12px]">
          <span> {name} </span>
          <span
            className={`ml-3 flex items-center rounded-sm bg-primary-hover px-1.5 py-[0.1em] text-muted`}
          >
            <RenderIcons filteredShortcut={fixedShortcut} />
          </span>
        </div>
      )}
    </>
  );
}
