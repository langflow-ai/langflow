import { forwardRef, type ReactNode, useEffect, useState } from "react";
import { track } from "@/customization/utils/analytics";
import useFlowStore from "@/stores/flowStore";
import type { FlowType } from "@/types/flow";
import IconComponent from "../../components/common/genericIconComponent";
import EditFlowSettings from "../../components/core/editFlowSettingsComponent";
import { Checkbox } from "../../components/ui/checkbox";
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
    const currentFlowOnPage = useFlowStore((state) => state.currentFlow);
    const currentFlow = props.flowData ?? currentFlowOnPage;
    const isBuilding = useFlowStore((state) => state.isBuilding);
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
        onSubmit={async () => {
          try {
            if (checked) {
              await downloadFlow(
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
              setOpen(false);
              track("Flow Exported", { flowId: currentFlow!.id });
            } else {
              await downloadFlow(
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
              );

              setSuccessData({
                title: "Flow exported successfully",
              });
              setOpen(false);
              track("Flow Exported", { flowId: currentFlow!.id });
            }
          } catch (error) {
            console.error("Error exporting flow:", error);
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
        </BaseModal.Content>

        <BaseModal.Footer
          submit={{
            label: "Export",
            loading: isBuilding,
            dataTestId: "modal-export-button",
          }}
        />
      </BaseModal>
    );
  },
);
export default ExportModal;
