import ConfirmationModal from "../confirmationModal";

export function BuildInProgressModal({
  onStopBuild,
  onCancel,
}: {
  onStopBuild: () => void;
  onCancel: () => void;
}): JSX.Element {
  return (
    <ConfirmationModal
      open={true}
      onClose={onCancel}
      title="Flow is outdated"
      cancelText="Create Copy"
      confirmationText="Overwrite"
      onConfirm={onStopBuild}
      onCancel={onCancel}
      size="x-small"
    >
      <ConfirmationModal.Content>
        The flow you are trying to save is outdated. Do you want to overwrite
        the existing flow?
      </ConfirmationModal.Content>
    </ConfirmationModal>
  );
}
