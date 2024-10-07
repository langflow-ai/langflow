import { convertTestName } from "@/components/storeCardComponent/utils/convert-test-name";

export default function HandleTooltipComponent({
  isInput,
  tooltipTitle,
  colors,
  isConnecting,
  isCompatible,
  isSameNode,
}: {
  isInput: boolean;
  colors: string[];
  tooltipTitle: string;
  isConnecting: boolean;
  isCompatible: boolean;
  isSameNode: boolean;
}) {
  const tooltips = tooltipTitle.split("\n");
  const plural = tooltips.length > 1 ? "s" : "";
  return (
    <div className="py-1.5 font-medium text-muted-foreground">
      {isSameNode ? (
        "Can't connect to the same node"
      ) : (
        <div className="flex items-start gap-1.5">
          {isConnecting ? (
            isCompatible ? (
              <span>
                <span className="font-semibold text-foreground">Connect</span>{" "}
                to
              </span>
            ) : (
              <span>Incompatible with</span>
            )
          ) : (
            <span className="text-foreground">
              {isInput ? `Input${plural}` : `Output${plural}`}:{" "}
            </span>
          )}
          {tooltips.map((word, index) => (
            <div
              className="rounded-sm px-1.5 text-background"
              style={{ backgroundColor: colors[index] }}
              data-testid={`${isInput ? "input" : "output"}-tooltip-${convertTestName(word)}`}
            >
              {word}
            </div>
          ))}
          {isConnecting && <span>{isInput ? `input` : `output`}</span>}
        </div>
      )}
      {!isConnecting && (
        <div className="mt-2 flex flex-col gap-0.5 text-xs">
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
