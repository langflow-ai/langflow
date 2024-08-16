import ForwardedIconComponent from "@/components/genericIconComponent";
import { FlowType } from "@/types/flow";
import { truncate } from "lodash";
import ConfirmationModal from "../confirmationModal";

export function SaveChangesModal({
  onSave,
  onProceed,
  onCancel,
  flow,
  lastSaved,
  autoSave,
}: {
  onSave: () => void;
  onProceed: () => void;
  onCancel: () => void;
  flow: FlowType;
  lastSaved: string | undefined;
  autoSave: boolean;
}): JSX.Element {
  return (
    <ConfirmationModal
      open={true}
      onClose={onCancel}
      destructiveCancel
      title={truncate(flow.name, { length: 32 }) + " has unsaved changes"}
      cancelText={"Exit anyway"}
      confirmationText={"Save and Exit"}
      onConfirm={onSave}
      onCancel={onProceed}
      size="x-small"
    >
      <ConfirmationModal.Content>
        <div className="mb-4 flex w-full items-center gap-3 rounded-md bg-yellow-100 px-4 py-2 text-yellow-800">
          <ForwardedIconComponent name="info" className="h-5 w-5" />
          Last saved: {lastSaved ?? "Never"}
        </div>

        {autoSave ? (
          <>
            This flow was not saved yet by auto-saving. Save and exit to ensure
            all of your changes are saved.
          </>
        ) : (
          <>
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
