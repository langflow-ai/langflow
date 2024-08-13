import ConfirmationModal from "../confirmationModal";

export function SaveChangesModal({ onSave, onProceed, onCancel }) {
  return (
    <ConfirmationModal
      open={true}
      onClose={onCancel}
      destructiveCancel
      title={"Exit without saving?"}
      cancelText={"Exit anyway"}
      confirmationText={"Save and Exit"}
      icon={"Save"}
      onConfirm={onSave}
      onCancel={onProceed}
      size="x-small"
    >
      <ConfirmationModal.Content>
        You have unsaved changes. Would you like to save them before exiting?
      </ConfirmationModal.Content>
    </ConfirmationModal>
  );
}
