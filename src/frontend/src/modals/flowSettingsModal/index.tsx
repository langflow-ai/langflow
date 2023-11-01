import { useContext, useEffect, useState } from "react";
import EditFlowSettings from "../../components/EditFlowSettingsComponent";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { SETTINGS_DIALOG_SUBTITLE } from "../../constants/constants";
import { FlowsContext } from "../../contexts/flowsContext";
import { FlowSettingsPropsType } from "../../types/components";
import BaseModal from "../baseModal";

export default function FlowSettingsModal({
  open,
  setOpen,
}: FlowSettingsPropsType): JSX.Element {
  const { flows, tabId, updateFlow, saveFlow } = useContext(FlowsContext);
  const flow = flows.find((f) => f.id === tabId);
  useEffect(() => {
    setName(flow!.name);
    setDescription(flow!.description);
  }, [flow!.name, flow!.description]);
  const [name, setName] = useState(flow!.name);
  const [description, setDescription] = useState(flow!.description);
  const [invalidName, setInvalidName] = useState(false);

  function handleClick(): void {
    let savedFlow = flows.find((flow) => flow.id === tabId);
    savedFlow!.name = name;
    savedFlow!.description = description;
    saveFlow(savedFlow!);
    setOpen(false);
  }
  return (
    <BaseModal open={open} setOpen={setOpen} size="smaller">
      <BaseModal.Header description={SETTINGS_DIALOG_SUBTITLE}>
        <span className="pr-2">Settings</span>
        <IconComponent name="Settings2" className="mr-2 h-4 w-4 " />
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
        />
      </BaseModal.Content>

      <BaseModal.Footer>
        <Button disabled={invalidName} onClick={handleClick} type="submit">
          Save
        </Button>
      </BaseModal.Footer>
    </BaseModal>
  );
}
