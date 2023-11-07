import { ReactNode, forwardRef, useContext, useEffect, useState } from "react";
import EditFlowSettings from "../../components/EditFlowSettingsComponent";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
import { EXPORT_DIALOG_SUBTITLE } from "../../constants/constants";
import { alertContext } from "../../contexts/alertContext";
import { FlowsContext } from "../../contexts/flowsContext";
import { typesContext } from "../../contexts/typesContext";
import { removeApiKeys } from "../../utils/reactflowUtils";
import BaseModal from "../baseModal";

const ExportModal = forwardRef(
  (props: { children: ReactNode }, ref): JSX.Element => {
    const { flows, tabId, downloadFlow } = useContext(FlowsContext);
    const { reactFlowInstance } = useContext(typesContext);
    const { setNoticeData } = useContext(alertContext);
    const [checked, setChecked] = useState(true);
    const flow = flows.find((f) => f.id === tabId);
    useEffect(() => {
      setName(flow!.name);
      setDescription(flow!.description);
    }, [flow!.name, flow!.description]);
    const [name, setName] = useState(flow!.name);
    const [description, setDescription] = useState(flow!.description);
    const [open, setOpen] = useState(false);

    return (
      <BaseModal size="smaller" open={open} setOpen={setOpen}>
        <BaseModal.Trigger>{props.children}</BaseModal.Trigger>
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
            flows={flows}
            tabId={tabId}
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
            <label htmlFor="terms" className="export-modal-save-api text-sm ">
              Save with my API keys
            </label>
          </div>
          <span className="text-xs text-destructive">
            Caution: Uncheck this box only removes API keys from fields
            specifically designated for API keys.
          </span>
        </BaseModal.Content>

        <BaseModal.Footer>
          <Button
            onClick={() => {
              if (checked) {
                downloadFlow(
                  {
                    id: tabId,
                    data: reactFlowInstance?.toObject()!,
                    description,
                    name,
                  },
                  name!,
                  description
                );
                setNoticeData({
                  title:
                    "Warning: Critical data, JSON file may include API keys.",
                });
              } else
                downloadFlow(
                  removeApiKeys({
                    id: tabId,
                    data: reactFlowInstance?.toObject()!,
                    description,
                    name,
                  }),
                  name!,
                  description
                );
              setOpen(false);
            }}
            type="submit"
          >
            Download Flow
          </Button>
        </BaseModal.Footer>
      </BaseModal>
    );
  }
);
export default ExportModal;
