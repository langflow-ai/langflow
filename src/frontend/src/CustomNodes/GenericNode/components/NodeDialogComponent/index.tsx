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
import useFlowStore from "@/stores/flowStore";
import { InputFieldType } from "@/types/api";

export const NodeDialog = ({
  open,
  onClose,
  dialogInputs,
  nodeId,
  name,
}: {
  open: boolean;
  onClose: () => void;
  dialogInputs: any;
  nodeId: string;
  name: string;
}) => {
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);

  interface ValueObject {
    value: string;
  }

  const handleNewValue = (value: string | ValueObject, key: string) => {
    const rawValue =
      typeof value === "object" && value ? (value as ValueObject).value : value;

    const targetKey = name;

    const targetNode = nodes.find((node) => node.id === nodeId);
    if (!targetNode) return;

    if (targetKey) {
      const nodeTemplate = targetNode.data.node.template;
      nodeTemplate[targetKey].dialog_inputs.fields.data.node.template[
        key
      ].value = rawValue;
      setNode(nodeId, targetNode);
    }
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
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="default">{dialogInputs.functionality}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default NodeDialog;
