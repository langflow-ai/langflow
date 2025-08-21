import BaseModal from "@/modals/baseModal";
import SessionView from "../../sessionViewComponent/session-view";

export const SessionLogsModal = ({
  sessionId,
  flowId,
  open,
  setOpen,
}: {
  sessionId: string;
  flowId?: string;
  open: boolean;
  setOpen: (open: boolean) => void;
}) => {
  return (
    <BaseModal size="large" open={open} setOpen={setOpen}>
      <BaseModal.Content>
        <SessionView sessionId={sessionId} flowId={flowId} />
      </BaseModal.Content>
    </BaseModal>
  );
};
