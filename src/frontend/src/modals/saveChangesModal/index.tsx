import ForwardedIconComponent from "@/components/genericIconComponent";
import { truncate } from "lodash";
import ConfirmationModal from "../confirmationModal";

export function SaveChangesModal({
  onSave,
  onProceed,
  onCancel,
  flowName,
  unsavedChanges,
  lastSaved,
  autoSave,
}: {
  onSave: () => void;
  onProceed: () => void;
  onCancel: () => void;
  flowName: string;
  unsavedChanges: boolean;
  lastSaved: string | undefined;
  autoSave: boolean;
}): JSX.Element {
  return (
    <ConfirmationModal
      open={true}
      onClose={onCancel}
      destructiveCancel
      title={truncate(flowName, { length: 32 }) + " has unsaved changes"}
      cancelText={autoSave ? undefined : "Exit anyway"}
      confirmationText={"Save and Exit"}
      onConfirm={autoSave ? onProceed : onSave}
      onCancel={onProceed}
      loading={autoSave ? unsavedChanges : false}
      size="x-small"
    >
      <ConfirmationModal.Content>
        {autoSave ? (
          "Saving flow automatically..."
        ) : (
          <>
            <div className="mb-4 flex w-full items-center gap-3 rounded-md bg-yellow-100 px-4 py-2 text-yellow-800">
              <ForwardedIconComponent name="info" className="h-5 w-5" />
              Last saved: {lastSaved ?? "Never"}
            </div>
            Unsaved changes will be permanently lost.{" "}
            <a
              target="_blank"
              className="underline"
              href="https://docs.langflow.org/configuration-auto-saving"
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
