import { useEffect, useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCreateDatasetFromMessages } from "@/controllers/API/queries/datasets/use-create-dataset-from-messages";
import useAlertStore from "@/stores/alertStore";
import BaseModal from "../baseModal";

interface SessionInfo {
  id: string;
  messageCount: number;
  lastTimestamp: string;
}

interface CreateDatasetFromMessagesModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  flowId: string;
  sessions: SessionInfo[];
  selectedSessionId?: string | null;
}

export default function CreateDatasetFromMessagesModal({
  open,
  setOpen,
  flowId,
  sessions,
  selectedSessionId,
}: CreateDatasetFromMessagesModalProps): JSX.Element {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [showAllSessions, setShowAllSessions] = useState(false);
  const [selectedSessions, setSelectedSessions] = useState<Set<string>>(
    () => new Set(selectedSessionId ? [selectedSessionId] : []),
  );

  // Sync selected sessions when modal opens
  useEffect(() => {
    if (open) {
      setSelectedSessions(
        new Set(selectedSessionId ? [selectedSessionId] : []),
      );
    }
  }, [open, selectedSessionId]);

  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
    setErrorData: state.setErrorData,
    setSuccessData: state.setSuccessData,
  }));

  const createMutation = useCreateDatasetFromMessages({
    onSuccess: (data) => {
      setSuccessData({
        title: `Dataset "${data.name}" created with ${data.item_count} items`,
      });
      handleClose();
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to create dataset",
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            "An unknown error occurred",
        ],
      });
    },
  });

  const toggleSession = (id: string) => {
    setSelectedSessions((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // The current session (shown by default)
  const currentSession = sessions.find((s) => s.id === selectedSessionId);
  // Other sessions (shown when expanded)
  const otherSessions = sessions.filter((s) => s.id !== selectedSessionId);

  const totalMessages = useMemo(() => {
    return sessions
      .filter((s) => selectedSessions.has(s.id))
      .reduce((sum, s) => sum + s.messageCount, 0);
  }, [sessions, selectedSessions]);

  const estimatedTurns = Math.floor(totalMessages / 2);

  const handleSubmit = () => {
    if (!name.trim()) {
      setErrorData({
        title: "Validation error",
        list: ["Please provide a dataset name"],
      });
      return;
    }

    if (selectedSessions.size === 0) {
      setErrorData({
        title: "Validation error",
        list: ["Please select at least one session"],
      });
      return;
    }

    createMutation.mutate({
      name: name.trim(),
      description: description.trim() || undefined,
      session_ids: Array.from(selectedSessions),
      flow_id: flowId,
    });
  };

  const handleClose = () => {
    setOpen(false);
    setName("");
    setDescription("");
    setShowAllSessions(false);
    setSelectedSessions(new Set());
  };

  const renderSessionRow = (session: SessionInfo) => (
    <label
      key={session.id}
      className="flex cursor-pointer items-center gap-3 border-b px-3 py-2 last:border-b-0 hover:bg-accent/50"
    >
      <input
        type="checkbox"
        checked={selectedSessions.has(session.id)}
        onChange={() => toggleSession(session.id)}
        className="h-4 w-4 rounded border-input"
      />
      <div className="flex flex-1 items-center justify-between">
        <span className="text-sm">
          {session.id.length > 20
            ? `${session.id.slice(0, 20)}...`
            : session.id || "Default"}
        </span>
        <span className="text-xs text-muted-foreground">
          {session.messageCount} msgs
        </span>
      </div>
    </label>
  );

  if (!open) return <></>;

  return (
    <BaseModal open={open} setOpen={handleClose} size="small-h-full" onSubmit={handleSubmit}>
      <BaseModal.Header description="Create a Multi-Turn dataset from existing chat messages">
        <ForwardedIconComponent name="MessagesSquare" className="mr-2 h-4 w-4" />
        Create Dataset from Messages
      </BaseModal.Header>
      <BaseModal.Content className="flex flex-col gap-6 px-6 py-4">
        {/* Name */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="dataset-name">
            Dataset Name <span className="text-destructive">*</span>
          </Label>
          <Input
            id="dataset-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Agent conversations dataset"
          />
        </div>

        {/* Description */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="dataset-description">Description (optional)</Label>
          <Input
            id="dataset-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description of the dataset"
          />
        </div>

        {/* Sessions */}
        <div className="flex flex-col gap-2">
          <Label>Session</Label>
          <div className="rounded-md border">
            {!showAllSessions ? (
              <>
                {currentSession && renderSessionRow(currentSession)}
                {otherSessions.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowAllSessions(true)}
                    className="flex w-full items-center justify-center gap-1.5 px-3 py-2 text-xs text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors"
                  >
                    <ForwardedIconComponent name="ChevronDown" className="h-3 w-3" />
                    Include more sessions ({otherSessions.length})
                  </button>
                )}
              </>
            ) : (
              <>
                <div className="max-h-52 overflow-y-auto">
                  {currentSession && renderSessionRow(currentSession)}
                  {otherSessions.map(renderSessionRow)}
                </div>
                <button
                  type="button"
                  onClick={() => setShowAllSessions(false)}
                  className="flex w-full items-center justify-center gap-1.5 border-t px-3 py-2 text-xs text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors"
                >
                  <ForwardedIconComponent name="ChevronUp" className="h-3 w-3" />
                  Show less
                </button>
              </>
            )}
          </div>
        </div>

        {/* Preview */}
        <div className="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
          Will create ~{estimatedTurns} turns from {selectedSessions.size} conversation{selectedSessions.size !== 1 ? "s" : ""}
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: "Create Dataset",
          loading: createMutation.isPending,
          disabled:
            !name.trim() ||
            selectedSessions.size === 0 ||
            createMutation.isPending,
          dataTestId: "btn-create-dataset-from-messages",
        }}
      />
    </BaseModal>
  );
}
