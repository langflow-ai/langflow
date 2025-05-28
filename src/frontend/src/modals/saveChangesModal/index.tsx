import ForwardedIconComponent from "@/components/common/genericIconComponent";
import Loading from "@/components/ui/loading";
import { truncate } from "lodash";
import { useState } from "react";
import ConfirmationModal from "../confirmationModal";

export function SaveChangesModal({
  onSave,
  onProceed,
  onCancel,
  flowName,
  lastSaved,
  autoSave,
}: {
  onSave: () => void;
  onProceed: () => void;
  onCancel: () => void;
  flowName: string;
  lastSaved: string | undefined;
  autoSave: boolean;
}): JSX.Element {
  const [saving, setSaving] = useState(false);
  return (
    <ConfirmationModal
      open={true}
      onClose={onCancel}
      destructiveCancel
      title={
        (autoSave ? "Flow" : truncate(flowName, { length: 32 })) +
        " has unsaved changes"
      }
      cancelText={autoSave ? undefined : "Exit anyway"}
      confirmationText={autoSave ? undefined : "Save and Exit"}
      onConfirm={
        autoSave
          ? undefined
          : () => {
              setSaving(true);
              onSave();
            }
      }
      onCancel={onProceed}
      loading={autoSave ? true : saving}
      size="x-small"
    >
      <ConfirmationModal.Content>
        {autoSave ? (
          <div className="mb-4 flex w-full items-center gap-3 rounded-md bg-muted px-4 py-2 text-muted-foreground">
            <Loading className="h-5 w-5" />
            Saving your changes...
          </div>
        ) : (
          <>
            <div className="mb-4 flex w-full items-center gap-3 rounded-md bg-yellow-100 px-4 py-2 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-100">
              <ForwardedIconComponent name="Info" className="h-5 w-5" />
              Last saved: {lastSaved ?? "Never"}
            </div>
            Unsaved changes will be permanently lost.{" "}
            <a
              target="_blank"
              className="text-secondary underline"
              href="https://docs.langflow.org/configuration-auto-save"
            >
              Enable auto-saving
            </a>{" "}
            to avoid losing progress.
          </>
        )}
      </ConfirmationModal.Content>
    </ConfirmationModal>
  );
}
