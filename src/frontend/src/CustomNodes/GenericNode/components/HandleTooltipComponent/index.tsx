export default function HandleTooltipComponent({
  isInput,
  tooltipTitle,
  color,
  isConnecting,
  isCompatible,
}: {
  isInput: boolean;
  color: string;
  tooltipTitle: string;
  isConnecting: boolean;
  isCompatible: boolean;
}) {
  return (
    <div className="py-1.5 font-medium">
      <div className="flex items-start gap-1">
        {isConnecting ? (
          isCompatible ? (
            <span className="mr-1">
              <span className="font-semibold">Connect</span> to
            </span>
          ) : (
            <span className="mr-1">Incompatible with</span>
          )
        ) : (
          <span className="mr-1">{isInput ? "Input" : "Output"}: </span>
        )}
        <div
          className="rounded-sm px-1.5 text-background"
          style={{ backgroundColor: color }}
        >
          {tooltipTitle}
        </div>
        {isConnecting && (
          <span className="ml-1">{isInput ? "input" : "output"}</span>
        )}
      </div>
      {!isConnecting && (
        <div className="mt-2 flex flex-col gap-0.5 text-xs text-muted-foreground">
          <div>
            <b>Drag</b> to connect compatible {!isInput ? "inputs" : "outputs"}
          </div>
          <div>
            <b>Select</b> to filter compatible {!isInput ? "inputs" : "outputs"}{" "}
            and components
          </div>
        </div>
      )}
    </div>
  );
}
