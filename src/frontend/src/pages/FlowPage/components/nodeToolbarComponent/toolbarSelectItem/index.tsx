import ForwardedIconComponent from "../../../../../components/common/genericIconComponent";
import RenderIcons from "../../../../../components/common/renderIconComponent";
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
        className={`mt-[0.15em] mr-2 h-4 w-4 ${ping && "animate-pulse text-green-500"}`}
      />
      <span>{value}</span>
      <span
        className={`bg-muted text-muted-foreground absolute top-[0.43em] right-2 flex items-center rounded-sm px-1.5 py-[0.1em]`}
      >
        <RenderIcons filteredShortcut={fixedShortcut} />
      </span>
    </div>
  );
}
