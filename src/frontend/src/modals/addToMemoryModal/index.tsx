import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useGetMemories } from "@/controllers/API/queries/memories/use-get-memories";
import { useAddMessagesToMemory } from "@/controllers/API/queries/memories/use-add-messages-to-memory";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import BaseModal from "../baseModal";

interface AddToMemoryModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  messageIds: string[];
  onSuccess?: () => void;
}

export default function AddToMemoryModal({
  open,
  setOpen,
  messageIds,
  onSuccess,
}: AddToMemoryModalProps): JSX.Element {
  const [selectedMemoryId, setSelectedMemoryId] = useState("");
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
    setErrorData: state.setErrorData,
    setSuccessData: state.setSuccessData,
  }));

  const { data: memories, isLoading: memoriesLoading } = useGetMemories(
    { flowId: currentFlowId ?? undefined },
    { enabled: !!currentFlowId },
  );

  const addMessagesMutation = useAddMessagesToMemory({
    onSuccess: () => {
      setSuccessData({
        title: `Added ${messageIds.length} message${messageIds.length !== 1 ? "s" : ""} to memory`,
      });
      setOpen(false);
      setSelectedMemoryId("");
      onSuccess?.();
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to add messages to memory",
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            "An unknown error occurred",
        ],
      });
    },
  });

  const handleSubmit = () => {
    if (!selectedMemoryId) {
      setErrorData({
        title: "Validation error",
        list: ["Please select a memory"],
      });
      return;
    }

    addMessagesMutation.mutate({
      memoryId: selectedMemoryId,
      message_ids: messageIds,
    });
  };

  const handleClose = () => {
    setOpen(false);
    setSelectedMemoryId("");
  };

  if (!open) return <></>;

  return (
    <BaseModal
      open={open}
      setOpen={handleClose}
      size="small-h-full"
      onSubmit={handleSubmit}
    >
      <BaseModal.Header description={`Add ${messageIds.length} message${messageIds.length !== 1 ? "s" : ""} to a memory`}>
        <ForwardedIconComponent name="Brain" className="mr-2 h-4 w-4" />
        Add to Memory
      </BaseModal.Header>
      <BaseModal.Content className="flex flex-col gap-6 px-6 py-4">
        {/* Memory selector */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="memory-select">
            Memory <span className="text-destructive">*</span>
          </Label>
          <Select
            value={selectedMemoryId}
            onValueChange={setSelectedMemoryId}
          >
            <SelectTrigger id="memory-select">
              <SelectValue
                placeholder={
                  memoriesLoading ? "Loading..." : "Select a memory"
                }
              />
            </SelectTrigger>
            <SelectContent>
              {memories?.map((memory) => (
                <SelectItem key={memory.id} value={memory.id}>
                  {memory.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Summary */}
        <div className="rounded-lg border border-border bg-muted/50 p-4">
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">
              {messageIds.length}
            </span>{" "}
            message{messageIds.length !== 1 ? "s" : ""} will be vectorized and
            added to the selected memory&apos;s knowledge base.
          </p>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: "Add to Memory",
          loading: addMessagesMutation.isPending,
          disabled: !selectedMemoryId,
        }}
      />
    </BaseModal>
  );
}
