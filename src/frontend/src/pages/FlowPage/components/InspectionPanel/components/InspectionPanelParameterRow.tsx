import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import NodeInputInfo from "@/CustomNodes/GenericNode/components/NodeInputInfo";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import { useTypesStore } from "@/stores/typesStore";
import type { NodeDataType } from "@/types/flow";
import { scapeJSONParse } from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";
import { getDefaultDisplay, isValueEmpty } from "../utils";

interface InspectionPanelParameterRowProps {
  data: NodeDataType;
  name: string;
  title: string;
}

export default function InspectionPanelParameterRow({
  data,
  name,
  title,
}: InspectionPanelParameterRowProps) {
  const { t } = useTranslation();
  const template = data.node?.template[name];
  const isOnCanvas = !(template?.advanced ?? false);
  const isApiEditable = template?.api_editable === true;
  const required = template?.required ?? false;
  const info = template?.info ?? "";
  const isToolModeActive =
    (data.node?.tool_mode ?? false) && (template?.tool_mode ?? false);

  const factoryValue = useTypesStore(
    (state) => state.templates[data.type]?.template?.[name]?.value,
  );

  const { handleOnNewValue } = useHandleOnNewValue({
    node: data.node!,
    nodeId: data.id,
    name,
  });

  const isConnected = useFlowStore(
    useCallback(
      (state) =>
        state.edges.some(
          (edge) =>
            edge.target === data.id &&
            edge.targetHandle &&
            scapeJSONParse(edge.targetHandle)?.fieldName === name,
        ),
      [data.id, name],
    ),
  );

  // Ticket LE-1810: disabled fields (connected handles / tool mode) can't be
  // called via the API, so exposing them is blocked. Exposure is also coupled
  // to being on the node — an off-node field isn't callable, so the API
  // toggle only unlocks once the parameter is added to the node.
  const isDisabledField = isConnected || isToolModeActive || !isOnCanvas;

  const handleToggleVisibility = useCallback(() => {
    handleOnNewValue({ advanced: isOnCanvas });
  }, [handleOnNewValue, isOnCanvas]);

  const handleToggleApiEditable = useCallback(() => {
    handleOnNewValue({ api_editable: !isApiEditable });
  }, [handleOnNewValue, isApiEditable]);

  // The green "on" state mirrors EFFECTIVE exposure (what the snippets
  // advertise), not the raw persisted flag — a flag lingering on an off-node
  // or connected field stays inert and must not read as exposed.
  const isEffectivelyExposed = isApiEditable && !isDisabledField;

  // Hiding a required field with no value would fail validation at run time
  // with the culprit no longer visible on the node — block removing it.
  const isRequiredAndEmpty = required && isValueEmpty(template);

  const defaultDisplay = getDefaultDisplay(template, factoryValue);
  const defaultText =
    "token" in defaultDisplay
      ? t(`inspectionPanel.default.${defaultDisplay.token}`)
      : defaultDisplay.text;
  // Without a factory template for this field the preview falls back to the
  // LIVE value — label it "Value" instead of claiming it is the default.
  const previewLabel =
    factoryValue !== undefined
      ? t("inspectionPanel.defaultLabel")
      : t("inspectionPanel.valueLabel");

  return (
    <div
      className={cn(
        "group flex items-center justify-between gap-3 border-b border-border/50 px-3 py-2.5 last:border-b-0",
        !isOnCanvas && "opacity-80",
      )}
      data-testid={`inspector-param-${name}`}
    >
      <div className="flex min-w-0 flex-col gap-0.5">
        <div className="flex items-center gap-1">
          <span
            className={cn(
              "truncate text-sm font-medium",
              !isOnCanvas && "text-muted-foreground",
            )}
          >
            {title}
          </span>
          {required && <span className="text-destructive">*</span>}
          {info !== "" && (
            <ShadTooltip content={<NodeInputInfo info={info} />}>
              {/* Focusable so keyboard users can reach the help text —
                  Radix tooltips open on focus as well as hover. */}
              <button
                type="button"
                className="cursor-help rounded-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                aria-label={`${title} info`}
              >
                <IconComponent
                  name="Info"
                  strokeWidth={ICON_STROKE_WIDTH}
                  className="ml-0.5 h-3 w-3 text-placeholder"
                />
              </button>
            </ShadTooltip>
          )}
        </div>
        <span className="truncate text-xs text-muted-foreground">
          {previewLabel}: {defaultText}
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <ShadTooltip
          content={
            !isOnCanvas
              ? t("inspectionPanel.apiNeedsOnNode")
              : isDisabledField
                ? t("inspectionPanel.apiDisabledField")
                : isApiEditable
                  ? t("inspectionPanel.apiDisable")
                  : t("inspectionPanel.apiEnable")
          }
          avoidCollisions
        >
          {/* A disabled button emits no pointer events, so the tooltip would
              never open — the span carries the hover and the button goes
              pointer-events-none while disabled. */}
          <span
            className={cn(
              "inline-flex",
              isDisabledField && "cursor-not-allowed",
            )}
          >
            <Button
              unstyled
              ignoreTitleCase
              onClick={handleToggleApiEditable}
              disabled={isDisabledField}
              className={cn(
                "flex h-6 items-center justify-center rounded-md border px-2 text-[10px] font-semibold transition-colors",
                isEffectivelyExposed
                  ? "border-accent-emerald bg-accent-emerald/10 text-accent-emerald-foreground"
                  : "border-border text-muted-foreground hover:text-foreground",
                isDisabledField && "pointer-events-none opacity-50",
              )}
              data-testid={`inspector-api-${name}`}
              aria-pressed={isEffectivelyExposed}
              aria-label={`${title} API`}
            >
              API
            </Button>
          </span>
        </ShadTooltip>
        {isOnCanvas ? (
          <ShadTooltip
            content={
              isConnected
                ? t("inspection.cannotChangeVisibility")
                : isRequiredAndEmpty
                  ? t("inspectionPanel.cannotRemoveRequired")
                  : t("inspectionPanel.remove")
            }
            avoidCollisions
          >
            {/* Same disabled-button hover fix as the API toggle above. */}
            <span
              className={cn(
                "inline-flex",
                (isConnected || isRequiredAndEmpty) && "cursor-not-allowed",
              )}
            >
              <Button
                unstyled
                onClick={handleToggleVisibility}
                disabled={isConnected || isRequiredAndEmpty}
                className={cn(
                  // min-w matches the Add button so the API column stays
                  // aligned across rows regardless of the action label.
                  "flex h-6 min-w-[4.5rem] items-center justify-center rounded-md bg-muted px-2 text-xs text-foreground transition-colors hover:bg-muted-foreground/20",
                  (isConnected || isRequiredAndEmpty) &&
                    "pointer-events-none opacity-50",
                )}
                data-testid={`inspector-remove-${name}`}
                aria-label={`${t("inspectionPanel.remove")} ${title}`}
              >
                {t("inspectionPanel.remove")}
              </Button>
            </span>
          </ShadTooltip>
        ) : (
          <Button
            unstyled
            onClick={handleToggleVisibility}
            className="flex h-6 min-w-[4.5rem] items-center justify-center gap-0.5 rounded-md px-2 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            data-testid={`inspector-add-${name}`}
            aria-label={`${t("inspectionPanel.add")} ${title}`}
          >
            <IconComponent
              name="Plus"
              strokeWidth={ICON_STROKE_WIDTH}
              className="h-3 w-3"
            />
            {t("inspectionPanel.add")}
          </Button>
        )}
      </div>
    </div>
  );
}
