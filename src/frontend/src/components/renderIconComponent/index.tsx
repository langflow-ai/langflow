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
    <>
      {isMac ? (
        <ForwardedIconComponent name="Command" className="h-4 w-4" />
      ) : (
        filteredShortcut[0]
      )}
      <ForwardedIconComponent name="ArrowBigUp" className="ml-1 h-5 w-5" />
      {filteredShortcut.map((key, idx) => {
        if (idx > 0) {
          return <span className="ml-1"> {key.toUpperCase()} </span>;
        }
      })}
    </>
  ) : (
    <>
      {shortcutWPlus[0].toLowerCase() === "space" ? (
        "Space"
      ) : shortcutWPlus[0].length <= 1 ? (
        shortcutWPlus[0]
      ) : isMac ? (
        <ForwardedIconComponent name="Command" className="h-4 w-4" />
      ) : (
        shortcutWPlus[0]
      )}
      {shortcutWPlus.map((key, idx) => {
        if (idx > 0) {
          return <span className="ml-0.5"> {key.toUpperCase()} </span>;
        }
      })}
    </>
  );
}
