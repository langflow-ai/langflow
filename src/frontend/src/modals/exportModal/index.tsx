import { ReactNode, forwardRef, useContext, useState } from "react";
import EditFlowSettings from "../../components/EditFlowSettingsComponent";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
import { EXPORT_DIALOG_SUBTITLE } from "../../constants/constants";
import { TabsContext } from "../../contexts/tabsContext";
import { removeApiKeys } from "../../utils/reactflowUtils";
import BaseModal from "../baseModal";

const ExportModal = forwardRef((props: { children: ReactNode }, ref) => {
  const { flows, tabId, updateFlow, downloadFlow, saveFlow } =
    useContext(TabsContext);
  const [checked, setChecked] = useState(false);
  const [name, setName] = useState(
    flows.find((flow) => flow.id === tabId).name
  );
  const [invalidName, setInvalidName] = useState(false);
  const [description, setDescription] = useState(
    flows.find((flow) => flow.id === tabId).description
  );
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
          invalidName={invalidName}
          setInvalidName={setInvalidName}
          name={name}
          description={description}
          flows={flows}
          tabId={tabId}
          setName={setName}
          setDescription={setDescription}
          updateFlow={updateFlow}
        />
        <div className="mt-3 flex items-center space-x-2">
          <Checkbox
            id="terms"
            onCheckedChange={(event: boolean) => {
              setChecked(event);
            }}
          />
          <label htmlFor="terms" className="export-modal-save-api text-sm ">
            Save with my API keys
          </label>
        </div>
      </BaseModal.Content>

      <BaseModal.Footer>
        <Button
          onClick={() => {
            if (checked)
              downloadFlow(
                flows.find((flow) => flow.id === tabId),
                name,
                description
              );
            else
              downloadFlow(
                removeApiKeys(flows.find((flow) => flow.id === tabId)),
                name,
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
});
export default ExportModal;
