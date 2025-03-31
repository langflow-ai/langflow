import { ParameterRenderComponent } from "@/components/core/parameterRenderComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getCustomParameterTitle } from "@/customization/components/custom-parameter";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import useFlowStore from "@/stores/flowStore";
import { InputFieldType } from "@/types/api";
import { cloneDeep } from "lodash";

export const NodeDialog = ({
  open,
  onClose,
  dialogInputs,
  nodeId,
}: {
  open: boolean;
  onClose: () => void;
  dialogInputs: any;
  nodeId: string;
}) => {
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);

  const handleNewValue = (value: string, key: string) => {
    let rawValue = value;

    if (typeof value === "object" && value) {
      rawValue = (value as { value: string }).value;
    }

    const template = cloneDeep(dialogInputs?.fields?.data?.node?.template);
    template[key].value = value;

    const newNode = cloneDeep(nodes.find((node) => node.id === nodeId));
    if (newNode) {
      const template = newNode.data.node.template;
      const databaseFields = template.database_name.dialog_inputs.fields;
      const nodeTemplate = databaseFields.data.node.template;

      nodeTemplate[key].value = rawValue;
    }
    setNode(nodeId, newNode!);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-[700px] gap-2 px-1 py-6">
        <DialogHeader className="px-5 pb-3">
          <DialogTitle>
            <div className="flex items-center">
              <span className="pb-2">
                {dialogInputs.fields?.data?.node?.display_name}
              </span>
            </div>
          </DialogTitle>
          <DialogDescription>
            <div className="flex items-center gap-2">
              {dialogInputs.fields?.data?.node?.description}
            </div>
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-5 overflow-y-auto px-5">
          {Object.entries(dialogInputs?.fields?.data?.node?.template ?? {}).map(
            ([key, value]) => (
              <div key={key}>
                <div>
                  {getCustomParameterTitle({
                    title:
                      dialogInputs?.fields?.data?.node?.template[key]
                        .display_name ?? "",
                    nodeId,
                    isFlexView: false,
                  })}
                </div>
                <ParameterRenderComponent
                  handleOnNewValue={(value: string) =>
                    handleNewValue(value, key)
                  }
                  name={key}
                  nodeId={nodeId}
                  templateData={value as Partial<InputFieldType>}
                  templateValue={
                    dialogInputs?.fields?.data?.node?.template[key].value
                  }
                  editNode={false}
                  handleNodeClass={() => {}}
                  nodeClass={dialogInputs.fields?.data?.node}
                  disabled={false}
                  placeholder=""
                  isToolMode={false}
                />
              </div>
            ),
          )}
        </div>

        <DialogFooter className="px-5 pt-3">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button>{dialogInputs.functionality}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default NodeDialog;
