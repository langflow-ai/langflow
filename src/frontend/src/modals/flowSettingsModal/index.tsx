import useSaveFlow from "@/hooks/flows/use-save-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import EditFlowSettings from "../../components/core/editFlowSettingsComponent";
import { SETTINGS_DIALOG_SUBTITLE } from "../../constants/constants";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { FlowSettingsPropsType } from "../../types/components";
import { FlowType } from "../../types/flow";
import { isEndpointNameValid } from "../../utils/utils";
import BaseModal from "../baseModal";

export default function FlowSettingsModal({
  open,
  setOpen,
}: FlowSettingsPropsType): JSX.Element {
  const saveFlow = useSaveFlow();
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const flows = useFlowsManagerStore((state) => state.flows);
  useEffect(() => {
    setName(currentFlow!.name);
    setDescription(currentFlow!.description);
  }, [currentFlow?.name, currentFlow?.description, open]);

  const [name, setName] = useState(currentFlow!.name);
  const [description, setDescription] = useState(currentFlow!.description);
  const [endpoint_name, setEndpointName] = useState(
    currentFlow!.endpoint_name ?? "",
  );
  const [isSaving, setIsSaving] = useState(false);
  const [disableSave, setDisableSave] = useState(true);
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
  function handleClick(): void {
    setIsSaving(true);
    if (!currentFlow) return;
    const newFlow = cloneDeep(currentFlow);
    newFlow.name = name;
    newFlow.description = description;
    newFlow.endpoint_name =
      endpoint_name && endpoint_name.length > 0 ? endpoint_name : null;
    if (autoSaving) {
      saveFlow(newFlow)
        ?.then(() => {
          setOpen(false);
          setIsSaving(false);
          setSuccessData({ title: "Changes saved successfully" });
        })
        .catch(() => {
          setIsSaving(false);
        });
    } else {
      setCurrentFlow(newFlow);
      setOpen(false);
      setIsSaving(false);
    }
  }

  const [nameLists, setNameList] = useState<string[]>([]);

  useEffect(() => {
    if (flows) {
      const tempNameList: string[] = [];
      flows.forEach((flow: FlowType) => {
        tempNameList.push(flow.name);
      });
      setNameList(tempNameList.filter((name) => name !== currentFlow!.name));
    }
  }, [flows]);

  useEffect(() => {
    if (
      (!nameLists.includes(name) && currentFlow?.name !== name) ||
      currentFlow?.description !== description ||
      ((currentFlow?.endpoint_name ?? "") !== endpoint_name &&
        isEndpointNameValid(endpoint_name ?? "", 50))
    ) {
      setDisableSave(false);
    } else {
      setDisableSave(true);
    }
  }, [nameLists, currentFlow, description, endpoint_name, name]);
  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="smaller-h-full"
      onSubmit={handleClick}
    >
      <BaseModal.Header description={SETTINGS_DIALOG_SUBTITLE}>
        <span className="pr-2">Settings</span>
        <IconComponent name="Settings2" className="mr-2 h-4 w-4" />
      </BaseModal.Header>
      <BaseModal.Content>
        <EditFlowSettings
          invalidNameList={nameLists}
          name={name}
          description={description}
          endpointName={endpoint_name}
          setName={setName}
          setDescription={setDescription}
          setEndpointName={setEndpointName}
        />
      </BaseModal.Content>

      <BaseModal.Footer
        submit={{
          label: "Save",
          dataTestId: "save-flow-settings",
          disabled: disableSave,
          loading: isSaving,
        }}
      />
    </BaseModal>
  );
}
