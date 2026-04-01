import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { usePatchSnapshot } from "@/controllers/API/queries/deployments";
import type { FlowDeploymentAttachment } from "@/pages/MainPage/pages/deploymentsPage/types";
import useAlertStore from "@/stores/alertStore";

const NEW_DEPLOYMENT_VALUE = "__new__";

interface DeployChoiceDialogProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  attachments: FlowDeploymentAttachment[];
  snapshotVersionId: string;
  onChooseNew: () => void;
  onUpdateComplete: (deploymentName: string) => void;
}

export default function DeployChoiceDialog({
  open,
  setOpen,
  attachments,
  snapshotVersionId,
  onChooseNew,
  onUpdateComplete,
}: DeployChoiceDialogProps) {
  const [selected, setSelected] = useState<string>(NEW_DEPLOYMENT_VALUE);
  const [isUpdating, setIsUpdating] = useState(false);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutateAsync: patchSnapshot } = usePatchSnapshot();

  // Reset selection when the dialog opens with new attachments
  useEffect(() => {
    if (open) {
      setSelected(
        attachments.length === 1
          ? attachments[0].provider_snapshot_id
          : NEW_DEPLOYMENT_VALUE,
      );
    }
  }, [open, attachments]);

  const handleContinue = async () => {
    if (selected === NEW_DEPLOYMENT_VALUE) {
      onChooseNew();
      return;
    }

    const attachment = attachments.find(
      (a) => a.provider_snapshot_id === selected,
    );
    if (!attachment) return;

    setIsUpdating(true);
    try {
      await patchSnapshot({
        providerSnapshotId: attachment.provider_snapshot_id,
        flowVersionId: snapshotVersionId,
      });
      onUpdateComplete(attachment.deployment_name);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Something went wrong";
      setErrorData({
        title: "Failed to update deployment",
        list: [message],
      });
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (isUpdating) return;
        setOpen(nextOpen);
      }}
    >
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Deploy</DialogTitle>
          <DialogDescription>
            This flow already has existing deployments. Would you like to update
            one or create a new deployment?
          </DialogDescription>
        </DialogHeader>

        <RadioGroup value={selected} onValueChange={setSelected}>
          {attachments.map((attachment) => (
            <div
              key={attachment.provider_snapshot_id}
              className="flex items-center gap-3 rounded-lg border p-3"
            >
              <RadioGroupItem
                value={attachment.provider_snapshot_id}
                id={`deploy-${attachment.provider_snapshot_id}`}
              />
              <Label
                htmlFor={`deploy-${attachment.provider_snapshot_id}`}
                className="flex flex-1 cursor-pointer flex-col gap-0.5"
              >
                <span className="text-sm font-medium">
                  {attachment.deployment_name}
                </span>
                <span className="text-xs text-muted-foreground">
                  {attachment.deployment_type} deployment
                </span>
              </Label>
            </div>
          ))}

          <div className="flex items-center gap-3 rounded-lg border p-3">
            <RadioGroupItem value={NEW_DEPLOYMENT_VALUE} id="deploy-new" />
            <Label
              htmlFor="deploy-new"
              className="flex flex-1 cursor-pointer flex-col gap-0.5"
            >
              <span className="text-sm font-medium">Create new deployment</span>
              <span className="text-xs text-muted-foreground">
                Set up a new deployment from scratch
              </span>
            </Label>
          </div>
        </RadioGroup>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            disabled={isUpdating}
          >
            Cancel
          </Button>
          <Button onClick={handleContinue} disabled={isUpdating}>
            {isUpdating ? "Updating..." : "Continue"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
