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
import { InputFieldType } from "@/types/api";

export const NodeDialog = ({ open, onClose, dialogInputs }) => {
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
                    nodeId: "demo",
                    isFlexView: false,
                  })}
                </div>
                <ParameterRenderComponent
                  handleOnNewValue={() => {}}
                  name={key}
                  nodeId="demo"
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
