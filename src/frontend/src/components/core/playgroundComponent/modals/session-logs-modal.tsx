import ForwardedIconComponent from "@/components/common/genericIconComponent";
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
        <BaseModal.Header description="Inspect and edit all messages of the session.">
          <div className="flex h-fit w-32 items-center">
            <span className="pr-2">Session logs</span>
            <ForwardedIconComponent name="ScrollText" className="h-4 w-4" />
          </div>
        </BaseModal.Header>
        <div className="pt-4 h-full">
          <SessionView sessionId={sessionId} flowId={flowId} />
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
};
