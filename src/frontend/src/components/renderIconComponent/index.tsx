import { IS_MAC } from "@/constants/constants";
import { addPlusSignes, sortShortcuts } from "@/utils/utils";
import RenderKey from "./components/renderKey";

export default function RenderIcons({
  hasShift,
  filteredShortcut,
}: {
  isMac?: boolean;
  hasShift: boolean;
  filteredShortcut: string[];
}): JSX.Element {
  const shortcutList = addPlusSignes((hasShift? [...filteredShortcut,"shift"]: filteredShortcut).sort(sortShortcuts));
  return (
    <span className="flex items-center justify-center gap-0.5 text-xs">
      {shortcutList.map((key, index) => (
        <span key={index} className="text-xs">
          <RenderKey value={key} />
        </span>
      ))}
    </span>
  );
}
