import { useTranslation } from "react-i18next";
import { addPlusSignes, cn, sortShortcuts } from "@/utils/utils";
import RenderKey, { shortcutKeyLabel } from "./components/renderKey";

export default function RenderIcons({
  filteredShortcut = [],
  tableRender = false,
}: {
  filteredShortcut: string[];
  tableRender?: boolean;
}): JSX.Element {
  const { t } = useTranslation();
  const sortedShortcut = [...filteredShortcut].sort(sortShortcuts);
  const shortcutList = addPlusSignes(sortedShortcut);
  // Name the whole shortcut explicitly and hide the icon-based visuals:
  // name-from-contents doesn't survive WebKit's grid cell value computation,
  // so sr-only text alternatives inside the keys are never spoken there.
  const label = sortedShortcut.map((key) => shortcutKeyLabel(key, t)).join(" ");
  return (
    <span
      role="img"
      aria-label={label}
      className={cn(
        "flex items-center gap-0.5",
        tableRender ? "justify-start" : "justify-center text-xs",
      )}
    >
      {shortcutList.map((key, index) => (
        <span key={index} aria-hidden="true">
          <RenderKey value={key} tableRender={tableRender} />
        </span>
      ))}
    </span>
  );
}
