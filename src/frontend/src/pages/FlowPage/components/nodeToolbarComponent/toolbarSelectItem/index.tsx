import ForwardedIconComponent from "../../../../../components/genericIconComponent";
import { toolbarSelectItemProps } from "../../../../../types/components";

export default function ToolbarSelectItem({
  value,
  icon,
  style,
  dataTestId,
  ping,
  shortcut,
}: toolbarSelectItemProps) {
  let hasShift = false;
  const fixedShortcut = shortcut?.split("+");
  fixedShortcut.forEach((key) => {
    if (key.toLowerCase().includes("shift")) {
      hasShift = true;
    }
  });
  const filteredShortcut = fixedShortcut.filter(
    (key) => !key.toLowerCase().includes("shift"),
  );
  let shortcutWPlus = "";
  if (!hasShift) shortcutWPlus = filteredShortcut.join("+");

  return (
    <div className={`flex ${style}`} data-testid={dataTestId}>
      <ForwardedIconComponent
        name={icon}
        className={`   mr-2  ${icon === "Share3" ? "absolute left-2  top-[0.25em] h-6 w-6" : "mt-[0.15em] h-4 w-4"}   ${
          ping && "animate-pulse text-green-500"
        }`}
      />
      <span className={`${icon === "Share3" ? "ml-[1.8em]" : " "}`}>
        {value}
      </span>
      <span className={`absolute right-2 top-[0.43em] flex `}>
        {hasShift ? (
          <>
            {filteredShortcut[0]}
            <ForwardedIconComponent
              name="ArrowBigUp"
              className="ml-1 h-5 w-5"
            />
            {filteredShortcut.map((key, idx) => {
              if (idx > 0) {
                return <span className="ml-1"> {key.toUpperCase()} </span>;
              }
            })}
          </>
        ) : (
          shortcutWPlus
        )}
      </span>
    </div>
  );
}
