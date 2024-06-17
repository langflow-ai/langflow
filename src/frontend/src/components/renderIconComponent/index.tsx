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
    <span className="flex items-center justify-center gap-0.5 text-xs">
      {isMac ? (
        <ForwardedIconComponent name="Command" className="h-3 w-3" />
      ) : (
        filteredShortcut[0]
      )}
      <ForwardedIconComponent name="ArrowBigUp" className="h-4 w-4" />
      {filteredShortcut.map((key, idx) => {
        if (idx > 0) {
          return key.toUpperCase();
        }
        return null;
      })}
    </span>
  ) : (
    <span className="flex items-center justify-center gap-0.5 text-xs">
      {shortcutWPlus[0].toLowerCase() === "space" ? (
        "Space"
      ) : shortcutWPlus[0].length <= 1 ? (
        shortcutWPlus[0]
      ) : isMac ? (
        <ForwardedIconComponent name="Command" className="h-3 w-3" />
      ) : (
        <span className="flex items-center">{shortcutWPlus[0]}</span>
      )}
      {shortcutWPlus.map((key, idx) => {
        if (idx > 0) {
          return (
            <span key={idx} className="flex items-center">
              {key.toUpperCase()}
            </span>
          );
        }
        return null;
      })}
    </span>
  );
}
