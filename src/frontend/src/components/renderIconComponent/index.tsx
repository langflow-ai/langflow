import ForwardedIconComponent from "../genericIconComponent";

export default function RenderIcons({
  isMac,
  hasShift,
  filteredShortcut,
  shortcutWPlus,
}: {
  isMac: boolean;
  hasShift: boolean;
  filteredShortcut: string[];
  shortcutWPlus: string[];
}): JSX.Element {
  return hasShift ? (
    <span className="flex gap-0.5 text-xs">
      {isMac ? (
        <ForwardedIconComponent name="Command" className="h-3 w-3" />
      ) : (
        filteredShortcut[0]
      )}
      <ForwardedIconComponent name="ArrowBigUp" className=" h-4 w-4" />
      {filteredShortcut.map((key, idx) => {
        if (idx > 0) {
          return <span className=""> {key.toUpperCase()} </span>;
        }
      })}
    </span>
  ) : (
    <span className="flex gap-1 text-xs">
      {shortcutWPlus[0].toLowerCase() === "space" ? (
        "Space"
      ) : shortcutWPlus[0].length <= 1 ? (
        shortcutWPlus[0]
      ) : isMac ? (
        <ForwardedIconComponent name="Command" className="h-3 w-3" />
      ) : (
        shortcutWPlus[0]
      )}
      {shortcutWPlus.map((key, idx) => {
        if (idx > 0) {
          return <span className=""> {key.toUpperCase()} </span>;
        }
      })}
    </span>
  );
}
