import { ReactNode, forwardRef, useEffect, useState } from "react";
import EditFlowSettings from "../../components/EditFlowSettingsComponent";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
import { EXPORT_DIALOG_SUBTITLE } from "../../constants/constants";
import useAlertStore from "../../stores/alertStore";
import { useDarkStore } from "../../stores/darkStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { downloadFlow, removeApiKeys } from "../../utils/reactflowUtils";
import BaseModal from "../baseModal";

const ExportModal = forwardRef(
  (props: { children: ReactNode }, ref): JSX.Element => {
    const version = useDarkStore((state) => state.version);
    const setNoticeData = useAlertStore((state) => state.setNoticeData);
    const [checked, setChecked] = useState(true);
    const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
    useEffect(() => {
      setName(currentFlow!.name);
      setDescription(currentFlow!.description);
    }, [currentFlow!.name, currentFlow!.description]);
    const [name, setName] = useState(currentFlow!.name);
    const [description, setDescription] = useState(currentFlow!.description);
    const [open, setOpen] = useState(false);

    return (
      <BaseModal size="smaller-h-full" open={open} setOpen={setOpen}>
        <BaseModal.Trigger asChild>{props.children}</BaseModal.Trigger>
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
            <label htmlFor="terms" className="export-modal-save-api text-sm ">
              Save with my API keys
            </label>
          </div>
          <span className=" text-xs text-destructive ">
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
                    id: currentFlow!.id,
                    data: currentFlow!.data!,
                    description,
                    name,
                    last_tested_version: version,
                    is_component: false,
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
                    id: currentFlow!.id,
                    data: currentFlow!.data!,
                    description,
                    name,
                    last_tested_version: version,
                    is_component: false,
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
