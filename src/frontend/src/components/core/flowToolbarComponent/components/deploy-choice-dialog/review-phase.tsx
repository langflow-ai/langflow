import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useGetFlowVersionEntry } from "@/controllers/API/queries/flow-version/use-get-flow-version-entry";
import type { FlowAttachment } from "./types";

interface ReviewPhaseContentProps {
  attachment: FlowAttachment;
  flowId: string;
  newVersionTag: string;
  isBusy: boolean;
  onBack: () => void;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ReviewPhaseContent({
  attachment,
  flowId,
  newVersionTag,
  isBusy,
  onBack,
  onConfirm,
  onCancel,
}: ReviewPhaseContentProps) {
  const { data: currentVersion, isLoading: isLoadingVersion } =
    useGetFlowVersionEntry(
      { flowId, versionId: attachment.flow_version_id },
      { enabled: !!attachment.flow_version_id },
    );

  const currentVersionTag = currentVersion?.version_tag ?? "...";

  return (
    <>
      <DialogHeader>
        <DialogTitle>Review Update</DialogTitle>
        <DialogDescription>
          Review the version change before updating the deployment.
        </DialogDescription>
      </DialogHeader>

      <div className="flex flex-col gap-4">
        <div className="rounded-lg border p-4">
          <p className="text-sm font-medium">{attachment.deployment_name}</p>
          <p className="text-xs text-muted-foreground">
            {attachment.deployment_type} deployment
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex flex-1 flex-col items-center gap-1.5 rounded-lg border p-3">
            <span className="text-xs text-muted-foreground">Current</span>
            {isLoadingVersion ? (
              <ForwardedIconComponent
                name="Loader2"
                className="h-4 w-4 animate-spin text-muted-foreground"
              />
            ) : (
              <Badge variant="secondary">{currentVersionTag}</Badge>
            )}
          </div>

          <ForwardedIconComponent
            name="ArrowRight"
            className="h-4 w-4 shrink-0 text-muted-foreground"
          />

          <div className="flex flex-1 flex-col items-center gap-1.5 rounded-lg border p-3">
            <span className="text-xs text-muted-foreground">New</span>
            <Badge variant="default">{newVersionTag}</Badge>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between pt-4">
        <Button variant="ghost" onClick={onCancel} disabled={isBusy}>
          Cancel
        </Button>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={onBack} disabled={isBusy}>
            Back
          </Button>
          <Button onClick={onConfirm} disabled={isBusy || isLoadingVersion}>
            Update
          </Button>
        </div>
      </div>
    </>
  );
}
