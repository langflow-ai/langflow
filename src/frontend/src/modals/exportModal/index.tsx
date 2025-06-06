import { track } from "@/customization/utils/analytics";
import useFlowStore from "@/stores/flowStore";
import { FlowType } from "@/types/flow";
import { ReactNode, forwardRef, useEffect, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import EditFlowSettings from "../../components/core/editFlowSettingsComponent";
import { Checkbox } from "../../components/ui/checkbox";
import { Label } from "../../components/ui/label";
import { API_WARNING_NOTICE_ALERT } from "../../constants/alerts_constants";
import {
  ALERT_SAVE_WITH_API,
  EXPORT_DIALOG_SUBTITLE,
  SAVE_WITH_API_CHECKBOX,
} from "../../constants/constants";
import useAlertStore from "../../stores/alertStore";
import { useDarkStore } from "../../stores/darkStore";
import { downloadFlow, removeApiKeys } from "../../utils/reactflowUtils";
import BaseModal from "../baseModal";
import { useGetDownloadFlowsPython } from "../../controllers/API/queries/flows/use-get-download-flows-python";

const ExportModal = forwardRef(
  (
    props: {
      children?: ReactNode;
      open?: boolean;
      setOpen?: (open: boolean) => void;
      flowData?: FlowType;
    },
    ref,
  ): JSX.Element => {
    const version = useDarkStore((state) => state.version);
    const setSuccessData = useAlertStore((state) => state.setSuccessData);
    const setNoticeData = useAlertStore((state) => state.setNoticeData);
    const [checked, setChecked] = useState(false);
    const [exportFormat, setExportFormat] = useState<"json" | "python">("json");
    const currentFlowOnPage = useFlowStore((state) => state.currentFlow);
    const currentFlow = props.flowData ?? currentFlowOnPage;
    const isBuilding = useFlowStore((state) => state.isBuilding);
    
    const { mutate: downloadPython, isPending: isDownloadingPython } = useGetDownloadFlowsPython({
      onSuccess: () => {
        setSuccessData({
          title: "Python code exported successfully",
        });
        setOpen(false);
        track("Flow Exported as Python", { flowId: currentFlow!.id });
      },
      onError: (error) => {
        console.error("Failed to export Python:", error);
        useAlertStore.getState().setErrorData({
          title: "Failed to export Python code",
          list: [error.message || "An error occurred while exporting"],
        });
      },
    });
    useEffect(() => {
      setName(currentFlow?.name ?? "");
      setDescription(currentFlow?.description ?? "");
    }, [currentFlow?.name, currentFlow?.description]);
    const [name, setName] = useState(currentFlow?.name ?? "");
    const [description, setDescription] = useState(
      currentFlow?.description ?? "",
    );

    const [customOpen, customSetOpen] = useState(false);
    const [open, setOpen] =
      props.open !== undefined && props.setOpen !== undefined
        ? [props.open, props.setOpen]
        : [customOpen, customSetOpen];

    return (
      <BaseModal
        size="smaller-h-full"
        open={open}
        setOpen={setOpen}
        onSubmit={() => {
          if (exportFormat === "python") {
            // Export as Python
            downloadPython({ ids: [currentFlow!.id] });
          } else {
            // Export as JSON (existing logic)
            if (checked) {
              downloadFlow(
                {
                  id: currentFlow!.id,
                  data: currentFlow!.data!,
                  description,
                  name,
                  last_tested_version: version,
                  endpoint_name: currentFlow!.endpoint_name,
                  is_component: false,
                  tags: currentFlow!.tags,
                },
                name!,
                description,
              );
              setNoticeData({
                title: API_WARNING_NOTICE_ALERT,
              });
            } else {
              downloadFlow(
                removeApiKeys({
                  id: currentFlow!.id,
                  data: currentFlow!.data!,
                  description,
                  name,
                  last_tested_version: version,
                  endpoint_name: currentFlow!.endpoint_name,
                  is_component: false,
                  tags: currentFlow!.tags,
                }),
                name!,
                description,
              ).then(() => {
                setSuccessData({
                  title: "Flow exported successfully",
                });
              });
            }
            setOpen(false);
            track("Flow Exported", { flowId: currentFlow!.id });
          }
        }}
      >
        <BaseModal.Trigger asChild>{props.children ?? <></>}</BaseModal.Trigger>
        <BaseModal.Header description={EXPORT_DIALOG_SUBTITLE}>
          <span className="pr-2">Export</span>
          <IconComponent
            name="Download"
            className="h-6 w-6 pl-1 text-foreground"
            aria-hidden="true"
          />
        </BaseModal.Header>
        <BaseModal.Content>
          <EditFlowSettings
            name={name}
            description={description}
            setName={setName}
            setDescription={setDescription}
          />
          
          {/* Export Format Selection */}
          <div className="mt-4 space-y-3">
            <Label className="text-sm font-medium">Export Format</Label>
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <input
                  type="radio"
                  id="json-format"
                  name="export-format"
                  value="json"
                  checked={exportFormat === "json"}
                  onChange={(e) => setExportFormat(e.target.value as "json" | "python")}
                  className="text-primary"
                />
                <Label htmlFor="json-format" className="text-sm cursor-pointer">
                  JSON (Langflow format)
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <input
                  type="radio"
                  id="python-format"
                  name="export-format"
                  value="python"
                  checked={exportFormat === "python"}
                  onChange={(e) => setExportFormat(e.target.value as "json" | "python")}
                  className="text-primary"
                />
                <Label htmlFor="python-format" className="text-sm cursor-pointer">
                  Python (Standalone code)
                </Label>
              </div>
            </div>
          </div>

          {exportFormat === "json" && (
            <>
              <div className="mt-3 flex items-center space-x-2">
                <Checkbox
                  id="terms"
                  checked={checked}
                  onCheckedChange={(event: boolean) => {
                    setChecked(event);
                  }}
                />
                <label htmlFor="terms" className="export-modal-save-api text-sm">
                  {SAVE_WITH_API_CHECKBOX}
                </label>
              </div>
              <span className="mt-1 text-xs text-destructive">
                {ALERT_SAVE_WITH_API}
              </span>
            </>
          )}

          {exportFormat === "python" && (
            <div className="mt-3 rounded-md bg-muted p-3">
              <p className="text-xs text-muted-foreground">
                Python export will generate standalone code that you can use in your own projects. 
                API keys will be automatically removed for security.
              </p>
            </div>
          )}
        </BaseModal.Content>

        <BaseModal.Footer
          submit={{
            label: exportFormat === "python" ? "Export Python" : "Export JSON",
            loading: exportFormat === "python" ? isDownloadingPython : isBuilding,
            dataTestId: "modal-export-button",
          }}
        />
      </BaseModal>
    );
  },
);
export default ExportModal;
