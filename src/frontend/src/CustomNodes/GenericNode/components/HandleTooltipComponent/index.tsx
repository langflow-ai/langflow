export default function HandleTooltipComponent({
  tooltipTitle,
  color,
}: {
  color: string;
  tooltipTitle: string;
}) {
  return (
    <div className="py-1.5 text-xs">
      <span className="mr-1">Type: </span>
      <span
        className="rounded-md px-2 pb-1 pt-0.5 text-background"
        style={{ backgroundColor: color }}
      >
        {tooltipTitle}
      </span>
    </div>
  );
}
