import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";

export default function InspectionPanelHeader() {
  const { t } = useTranslation();
  const setInspectionPanelVisible = useFlowStore(
    (state) => state.setInspectionPanelVisible,
  );
  // The per-field API toggle below is only enforced under the "declared"
  // policy. Stating the active one keeps the toggle from reading as a
  // guarantee the default deployment does not give.
  const tweaksPolicy = useUtilityStore((state) => state.tweaksPolicy);

  return (
    <div
      className="flex flex-col gap-1 px-4 py-3"
      data-testid="inspection-panel-header"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold" data-testid="panel-title">
          {t("inspectionPanel.title")}
        </span>
        <ShadTooltip content={t("inspectionPanel.close")}>
          <Button
            unstyled
            onClick={() => setInspectionPanelVisible(false)}
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            data-testid="inspection-panel-close"
            aria-label={t("inspectionPanel.close")}
          >
            <ForwardedIconComponent
              name="X"
              strokeWidth={ICON_STROKE_WIDTH}
              className="h-4 w-4"
            />
          </Button>
        </ShadTooltip>
      </div>
      <span
        className="text-xs text-muted-foreground"
        data-testid="panel-subtitle"
      >
        {t("inspectionPanel.subtitle")}
      </span>
      <span
        className="text-xs text-muted-foreground"
        data-testid={`panel-tweaks-policy-${tweaksPolicy}`}
      >
        {t(`inspectionPanel.policy.${tweaksPolicy}`)}
      </span>
    </div>
  );
}
