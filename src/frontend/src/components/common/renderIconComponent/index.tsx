import { addPlusSignes, cn, sortShortcuts } from "@/utils/utils";
import RenderKey from "./components/renderKey";

export default function RenderIcons({
  filteredShortcut = [],
  tableRender = false,
}: {
  filteredShortcut: string[];
  tableRender?: boolean;
}): JSX.Element {
  const shortcutList = addPlusSignes([...filteredShortcut].sort(sortShortcuts));
  return (
    <span
      className={cn(
        "flex items-center gap-0.5",
        tableRender ? "justify-start" : "justify-center text-xs",
      )}
    >
      {shortcutList.map((key, index) => (
        <span key={index}>
          <RenderKey value={key} tableRender={tableRender} />
        </span>
      ))}
    </span>
  );
}
