import ForwardedIconComponent from "../../../../../components/common/genericIconComponent";
import RenderIcons from "../../../../../components/common/renderIconComponent";
import { IS_MAC } from "../../../../../constants/constants";
import { toolbarSelectItemProps } from "../../../../../types/components";

export default function ToolbarSelectItem({
  value,
  icon,
  style,
  dataTestId,
  ping,
  shortcut,
}: toolbarSelectItemProps) {
  const fixedShortcut = shortcut?.split("+");
  return (
    <div className={`flex ${style}`} data-testid={dataTestId}>
      <ForwardedIconComponent
        name={icon}
        className={`mr-2 ${
          icon === "Share3"
            ? "absolute left-2 top-[0.25em] h-6 w-6"
            : "mt-[0.15em] h-4 w-4"
        } ${ping && "animate-pulse text-green-500"}`}
      />
      <span className={`${icon === "Share3" ? "ml-[1.8em]" : " "}`}>
        {value}
      </span>
      <span
        className={`absolute right-2 top-[0.43em] flex items-center rounded-sm bg-muted px-1.5 py-[0.1em] text-muted-foreground`}
      >
        <RenderIcons filteredShortcut={fixedShortcut} />
      </span>
    </div>
  );
}
