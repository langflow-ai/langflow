import ForwardedIconComponent from "@/components/common/genericIconComponent";
import BaseModal from "@/modals/baseModal";
import SessionView from "@/modals/IOModal/components/session-view";

export interface SessionLogsModalProps {
  sessionId: string;
  flowId?: string;
  open: boolean;
  setOpen: (open: boolean) => void;
}

export const SessionLogsModal = ({
  sessionId,
  flowId,
  open,
  setOpen,
}: SessionLogsModalProps) => {
  return (
    <BaseModal size="large" open={open} setOpen={setOpen} className="z-[300]">
      <BaseModal.Content>
        <BaseModal.Header description="Inspect and edit all messages of the session.">
          <div className="flex h-fit w-32 items-center">
            <span className="pr-2">Session logs</span>
            <ForwardedIconComponent name="ScrollText" className="h-4 w-4" />
          </div>
        </BaseModal.Header>
        <div className="pt-4 h-full">
          <SessionView session={sessionId} id={flowId} />
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
};
