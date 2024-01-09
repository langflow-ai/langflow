import { useEffect, useState } from "react";
import EditFlowSettings from "../../components/EditFlowSettingsComponent";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { SETTINGS_DIALOG_SUBTITLE } from "../../constants/constants";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { FlowSettingsPropsType } from "../../types/components";
import { FlowType } from "../../types/flow";
import BaseModal from "../baseModal";

export default function FlowSettingsModal({
  open,
  setOpen,
}: FlowSettingsPropsType): JSX.Element {
  const saveFlow = useFlowsManagerStore((state) => state.saveFlow);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const flows = useFlowsManagerStore((state) => state.flows);
  useEffect(() => {
    setName(currentFlow!.name);
    setDescription(currentFlow!.description);
  }, [currentFlow!.name, currentFlow!.description, open]);

  const [name, setName] = useState(currentFlow!.name);
  const [description, setDescription] = useState(currentFlow!.description);

  function handleClick(): void {
    currentFlow!.name = name;
    currentFlow!.description = description;
    saveFlow(currentFlow!);
    setOpen(false);
  }

  const [nameLists, setNameList] = useState<string[]>([]);

  useEffect(() => {
    const tempNameList: string[] = [];
    flows.forEach((flow: FlowType) => {
      if ((flow.is_component ?? false) === false) tempNameList.push(flow.name);
    });
    setNameList(tempNameList.filter((name) => name !== currentFlow!.name));
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
          disabled={nameLists.includes(name) && name !== currentFlow!.name}
          onClick={handleClick}
          type="submit"
        >
          Save
        </Button>
      </BaseModal.Footer>
    </BaseModal>
  );
}
