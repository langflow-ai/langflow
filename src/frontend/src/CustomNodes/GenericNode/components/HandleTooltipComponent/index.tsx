import { convertTestName } from "@/components/common/storeCardComponent/utils/convert-test-name";
import { Badge } from "@/components/ui/badge";
import { nodeColorsName } from "@/utils/styleUtils";

export default function HandleTooltipComponent({
  isInput,
  tooltipTitle,
  isConnecting,
  isCompatible,
  isSameNode,
  left,
}: {
  isInput: boolean;
  tooltipTitle: string;
  isConnecting: boolean;
  isCompatible: boolean;
  isSameNode: boolean;
  left: boolean;
}) {
  const tooltips = tooltipTitle.split("\n");
  const plural = tooltips.length > 1 ? "s" : "";

  return (
    <div className="font-medium">
      {isSameNode ? (
        "Can't connect to the same node"
      ) : (
        <div className="flex items-center gap-1.5">
          {isConnecting ? (
            isCompatible ? (
              <span>
                <span className="font-semibold">Connect</span> to
              </span>
            ) : (
              <span>Incompatible with</span>
            )
          ) : (
            <span className="text-xs">
              {isInput
                ? `Input${plural} type${plural}`
                : `Output${plural} type${plural}`}
              :{" "}
            </span>
          )}
          {tooltips.map((word, index) => (
            <Badge
              className="h-6 rounded-md p-1"
              key={`${index}-${word.toLowerCase()}`}
              style={{
                backgroundColor: left
                  ? `var(--color-datatype-${nodeColorsName[word]})`
                  : `var(--color-datatype-${nodeColorsName[word]}-foreground)`,
                color: left
                  ? `var(--color-datatype-${nodeColorsName[word]}-foreground)`
                  : `var(--color-datatype-${nodeColorsName[word]})`,
              }}
              data-testid={`${isInput ? "input" : "output"}-tooltip-${convertTestName(word)}`}
            >
              {word}
            </Badge>
          ))}
          {isConnecting && <span>{isInput ? `input` : `output`}</span>}
        </div>
      )}
      {!isConnecting && (
        <div className="mt-2 flex flex-col gap-0.5 text-xs leading-6">
          <div>
            <b>Drag</b> to connect compatible {!isInput ? "inputs" : "outputs"}
          </div>
          <div>
            <b>Click</b> to filter compatible {!isInput ? "inputs" : "outputs"}{" "}
            and components
          </div>
        </div>
      )}
    </div>
  );
}
