import { useTranslation } from "react-i18next";
import RenderIcons from "@/components/common/renderIconComponent";
import { cn, toCamelCase } from "@/utils/utils";

export default function ShortcutDisplay({
  display_name,
  name,
  shortcut,
  sidebar = false,
}: {
  display_name?: string;
  name?: string;
  shortcut: string;
  sidebar?: boolean;
}): JSX.Element {
  const { t } = useTranslation();
  const translatedName = name
    ? t(`shortcuts.name.${toCamelCase(name)}`, { defaultValue: display_name })
    : display_name;
  const fixedShortcut = shortcut?.split("+");
  return (
    <>
      {sidebar ? (
        <div className="flex justify-center">
          {translatedName && <span> {translatedName} </span>}
          <span
            className={cn(
              "flex h-4 w-4 items-center justify-center rounded-sm bg-muted text-muted-foreground",
              translatedName && "ml-3",
            )}
          >
            <RenderIcons filteredShortcut={fixedShortcut} />
          </span>
        </div>
      ) : (
        <div className="flex content-center items-center justify-center self-center text-xs">
          <span> {translatedName} </span>
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
