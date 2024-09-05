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
      title="Build in Progress"
      cancelText="Cancel"
      confirmationText="Stop Build"
      onConfirm={onStopBuild}
      onCancel={onCancel}
      size="x-small"
    >
      <ConfirmationModal.Content>
        The flow is currently building. Do you want to stop the build and exit?
      </ConfirmationModal.Content>
    </ConfirmationModal>
  );
}
