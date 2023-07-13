import { Download } from "lucide-react";
import { ReactNode, forwardRef, useContext, useState } from "react";
import EditFlowSettings from "../../components/EditFlowSettingsComponent";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
import { DialogTitle } from "../../components/ui/dialog";
import { EXPORT_DIALOG_SUBTITLE } from "../../constants";
import { PopUpContext } from "../../contexts/popUpContext";
import { TabsContext } from "../../contexts/tabsContext";
import { removeApiKeys } from "../../utils";
import BaseModal from "../baseModal";

const ExportModal = forwardRef((props: { children: ReactNode }, ref) => {
  const { closePopUp } = useContext(PopUpContext);
  const { flows, tabId, updateFlow, downloadFlow, saveFlow } =
    useContext(TabsContext);
  const [checked, setChecked] = useState(false);
  const [name, setName] = useState(flows.find((f) => f.id === tabId).name);
  const [description, setDescription] = useState(
    flows.find((f) => f.id === tabId).description
  );
  return (
    <BaseModal size="smaller">
      <BaseModal.Trigger>{props.children}</BaseModal.Trigger>
      <BaseModal.Header description={EXPORT_DIALOG_SUBTITLE}>
        <DialogTitle className="flex items-center">
          <span className="pr-2">Export</span>
          <Download
            strokeWidth={1.5}
            className="h-6 w-6 pl-1 text-primary "
            aria-hidden="true"
          />
        </DialogTitle>
      </BaseModal.Header>
      <BaseModal.Content>
        <EditFlowSettings
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
                flows.find((f) => f.id === tabId),
                name,
                description
              );
            else
              downloadFlow(
                removeApiKeys(flows.find((f) => f.id === tabId)),
                name,
                description
              );

            closePopUp();
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
