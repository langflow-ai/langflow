import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const tooltips = tooltipTitle.split("\n");
  const handleType = isInput ? t("node.input") : t("node.output");
  const oppositeHandleType = isInput ? t("node.outputs") : t("node.inputs");
  const handleTypeTitle = isInput
    ? t(tooltips.length > 1 ? "node.inputTypes" : "node.inputType")
    : t(tooltips.length > 1 ? "node.outputTypes" : "node.outputType");

  return (
    <div className="font-medium">
      {isSameNode ? (
        t("node.cannotConnectSameNode")
      ) : (
        <div className="flex items-center gap-1.5">
          {isConnecting ? (
            isCompatible ? (
              <span>
                <span className="font-semibold">{t("node.connectTo")}</span>
              </span>
            ) : (
              <span>{t("node.incompatibleWith")}</span>
            )
          ) : (
            <span className="text-xs">
              {t("node.handleTypeLabel", { type: handleTypeTitle })}{" "}
            </span>
          )}
          {tooltips.map((word, index) => (
            <Badge
              className="h-6 rounded-md p-1"
              key={`${index}-${word.toLowerCase()}`}
              style={{
                backgroundColor: left
                  ? `hsl(var(--datatype-${nodeColorsName[word]}))`
                  : `hsl(var(--datatype-${nodeColorsName[word]}-foreground))`,
                color: left
                  ? `hsl(var(--datatype-${nodeColorsName[word]}-foreground))`
                  : `hsl(var(--datatype-${nodeColorsName[word]}))`,
              }}
              data-testid={`${isInput ? "input" : "output"}-tooltip-${convertTestName(word)}`}
            >
              {word}
            </Badge>
          ))}
          {isConnecting && <span>{handleType}</span>}
        </div>
      )}
      {!isConnecting && (
        <div className="mt-2 flex flex-col gap-0.5 text-xs leading-6">
          <div>
            <b>{t("node.drag")}</b>{" "}
            {t("node.connectCompatible", { type: oppositeHandleType })}
          </div>
          <div>
            <b>{t("node.click")}</b>{" "}
            {t("node.filterCompatible", { type: oppositeHandleType })}
          </div>
        </div>
      )}
    </div>
  );
}
