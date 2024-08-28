export default function HandleTooltipComponent({
  isInput,
  tooltipTitle,
  color,
}: {
  isInput: boolean;
  color: string;
  tooltipTitle: string;
}) {
  return (
    <div className="py-1.5">
      <div className="flex items-start gap-1">
        <span className="mr-1">{isInput ? "Input" : "Output"}: </span>
        <div
          className="rounded-md px-2 pb-0.5 pt-0.5 text-xs text-background"
          style={{ backgroundColor: color }}
        >
          {tooltipTitle}
        </div>
      </div>

      <div className="mt-2 flex flex-col gap-0.5 text-xs text-muted-foreground">
        <div>
          <b>Drag</b> to connect compatible {!isInput ? "inputs" : "outputs"}
        </div>
        <div>
          <b>Select</b> to filter compatible {!isInput ? "inputs" : "outputs"}{" "}
          and components
        </div>
      </div>
    </div>
  );
}
