import { useContext, useEffect, useState } from "react";
import EditFlowSettings from "../../components/EditFlowSettingsComponent";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { SETTINGS_DIALOG_SUBTITLE } from "../../constants/constants";
import { FlowsContext } from "../../contexts/flowsContext";
import { FlowSettingsPropsType } from "../../types/components";
import { FlowType } from "../../types/flow";
import BaseModal from "../baseModal";

export default function FlowSettingsModal({
  open,
  setOpen,
}: FlowSettingsPropsType): JSX.Element {
  const { flows, tabId, saveFlow } = useContext(FlowsContext);
  const flow = flows.find((f) => f.id === tabId);
  useEffect(() => {
    setName(flow!.name);
    setDescription(flow!.description);
  }, [flow!.name, flow!.description]);
  const [name, setName] = useState(flow!.name);
  const [description, setDescription] = useState(flow!.description);

  function handleClick(): void {
    let savedFlow = flows.find((flow) => flow.id === tabId);
    savedFlow!.name = name;
    savedFlow!.description = description;
    saveFlow(savedFlow!);
    setOpen(false);
  }

  const [nameLists, setNameList] = useState<string[]>([]);

  useEffect(() => {
    const tempNameList: string[] = [];
    flows.forEach((flow: FlowType) => {
      if ((flow.is_component ?? false) === false) tempNameList.push(flow.name);
    });
    setNameList(tempNameList.filter((name) => name !== flow!.name));
  }, [flows]);

  return (
    <BaseModal open={open} setOpen={setOpen} size="smaller">
      <BaseModal.Header description={SETTINGS_DIALOG_SUBTITLE}>
        <span className="pr-2">Settings</span>
        <IconComponent name="Settings2" className="mr-2 h-4 w-4 " />
      </BaseModal.Header>
      <BaseModal.Content>
        <EditFlowSettings
          invalidNameList={nameLists}
          name={name}
          description={description}
          setName={setName}
          setDescription={setDescription}
        />
      </BaseModal.Content>

      <BaseModal.Footer>
        <Button
          disabled={nameLists.includes(name) && name !== flow!.name}
          onClick={handleClick}
          type="submit"
        >
          Save
        </Button>
      </BaseModal.Footer>
    </BaseModal>
  );
}
