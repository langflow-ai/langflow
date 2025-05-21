import { Button } from "@/components/ui/button";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { FlowType } from "@/types/flow";
import { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import EditFlowSettings from "../editFlowSettingsComponent";

export default function FlowSettingsComponent({
  flowData,
  close,
}: {
  flowData?: FlowType;
  close: () => void;
}): JSX.Element {
  const saveFlow = useSaveFlow();
  const currentFlow = useFlowStore((state) =>
    flowData ? undefined : state.currentFlow,
  );
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const flows = useFlowsManagerStore((state) => state.flows);
  const flow = flowData ?? currentFlow;
  const [name, setName] = useState(flow?.name ?? "");
  const [description, setDescription] = useState(flow?.description ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [disableSave, setDisableSave] = useState(true);
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);

  useEffect(() => {
    setName(flow?.name ?? "");
    setDescription(flow?.description ?? "");
  }, [flow?.name, flow?.description, flow?.endpoint_name, open]);

  function handleClick(): void {
    setIsSaving(true);
    if (!flow) return;
    const newFlow = cloneDeep(flow);
    newFlow.name = name;
    newFlow.description = description;

    if (autoSaving) {
      saveFlow(newFlow)
        ?.then(() => {
          setIsSaving(false);
          setSuccessData({ title: "Changes saved successfully" });
          close();
        })
        .catch(() => {
          setIsSaving(false);
        });
    } else {
      setCurrentFlow(newFlow);
      setIsSaving(false);
      close();
    }
  }

  const [nameLists, setNameList] = useState<string[]>([]);

  useEffect(() => {
    if (flows) {
      const tempNameList: string[] = [];
      flows.forEach((flow: FlowType) => {
        tempNameList.push(flow?.name ?? "");
      });
      setNameList(tempNameList.filter((name) => name !== (flow?.name ?? "")));
    }
  }, [flows]);

  useEffect(() => {
    if (
      (!nameLists.includes(name) && flow?.name !== name) ||
      flow?.description !== description
    ) {
      setDisableSave(false);
    } else {
      setDisableSave(true);
    }
  }, [nameLists, flow, description, name]);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <EditFlowSettings
          invalidNameList={nameLists}
          name={name}
          description={description}
          setName={setName}
          setDescription={setDescription}
        />
      </div>
      <div className="flex justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          data-testid="cancel-flow-settings"
          onClick={() => close()}
        >
          Cancel
        </Button>
        <Button
          variant="default"
          size="sm"
          data-testid="save-flow-settings"
          onClick={handleClick}
          loading={isSaving}
          disabled={disableSave}
        >
          Save
        </Button>
      </div>
    </div>
  );
}
