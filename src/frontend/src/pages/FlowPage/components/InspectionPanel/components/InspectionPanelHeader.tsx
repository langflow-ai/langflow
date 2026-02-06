import { useCallback, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import type { NodeDataType } from "@/types/flow";
import { ToolbarButton } from "../../nodeToolbarComponent/components/toolbar-button";
import { useShortcutsStore } from "@/stores/shortcuts";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";

interface InspectionPanelHeaderProps {
  data: NodeDataType;
  onClose?: () => void;
  isEditingFields?: boolean;
  onToggleEditFields?: () => void;
}

export default function InspectionPanelHeader({
  data,
  onClose,
  isEditingFields = false,
  onToggleEditFields,
}: InspectionPanelHeaderProps) {
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const handleCopyId = useCallback(() => {
    navigator.clipboard.writeText(data.id);
    setSuccessData({ title: "Component ID copied to clipboard" });
  }, [data.id, setSuccessData]);

  const openDocs = useCallback(() => {
    if (data.node?.documentation) {
      return customOpenNewTab(data.node.documentation);
    }
    setNoticeData({
      title: `${data.id} docs is not available at the moment.`,
    });
  }, [data.id, data.node?.documentation, setNoticeData]);

  const shortcuts = useShortcutsStore((state) => state.shortcuts);

  const hasDocs = (data.node?.documentation ?? "") !== "";

  return (
    <div className="flex flex-col gap-2 py-3 px-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold">
            {data.node?.display_name ?? data.type}
          </span>
          <ShadTooltip content="Click to copy full ID">
            <Badge
              variant="secondaryStatic"
              size="sm"
              className="shrink-0 cursor-pointer rounded-full px-2 text-[10px] font-normal hover:bg-muted-foreground/20"
              onClick={handleCopyId}
            >
              ID: {data.id.split("-").pop()}
            </Badge>
          </ShadTooltip>
        </div>
        <div className="flex items-center gap-1">
          {hasDocs && (
            <ToolbarButton
              icon="FileText"
              onClick={openDocs}
              shortcut={shortcuts.find((s) =>
                s.name.toLowerCase().startsWith("docs"),
              )}
              className="!text-muted-foreground"
              dataTestId="docs-button-modal"
            />
          )}
          <ToolbarButton
            icon={isEditingFields ? "Check" : "SlidersHorizontal"}
            onClick={onToggleEditFields}
            className={cn(
              isEditingFields
                ? "!text-primary"
                : "!text-muted-foreground",
            )}
            dataTestId="edit-fields-button"
          />
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Configure component settings and toggle parameter visibility.
      </p>
    </div>
  );
}
