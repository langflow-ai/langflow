import { Button } from "@/components/ui/button";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { FlowType } from "@/types/flow";
import * as Form from "@radix-ui/react-form";
import { cloneDeep } from "lodash";
import { useEffect, useRef, useState } from "react";
import EditFlowSettings from "../editFlowSettingsComponent";

export default function FlowSettingsComponent({
  flowData,
  close,
  open,
}: {
  flowData?: FlowType;
  close: () => void;
  open: boolean;
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
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    setName(flow?.name ?? "");
    setDescription(flow?.description ?? "");
  }, [flow?.name, flow?.description, flow?.endpoint_name, open]);

  function handleSubmit(event?: React.FormEvent<HTMLFormElement>): void {
    if (event) event.preventDefault();
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

  const submitForm = () => {
    formRef.current?.requestSubmit();
  };

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
    <Form.Root onSubmit={handleSubmit} ref={formRef}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <EditFlowSettings
            invalidNameList={nameLists}
            name={name}
            description={description}
            setName={setName}
            setDescription={setDescription}
            submitForm={submitForm}
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            data-testid="cancel-flow-settings"
            type="button"
            onClick={() => close()}
          >
            Cancel
          </Button>
          <Form.Submit asChild>
            <Button
              variant="default"
              size="sm"
              data-testid="save-flow-settings"
              loading={isSaving}
              disabled={disableSave}
            >
              Save
            </Button>
          </Form.Submit>
        </div>
      </div>
    </Form.Root>
  );
}
