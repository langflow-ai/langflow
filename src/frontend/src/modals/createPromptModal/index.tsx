import { useState, useEffect } from "react";
import BaseModal from "../baseModal";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreatePrompt } from "@/controllers/API/queries/prompt-library/use-create-prompt";
import useAlertStore from "@/stores/alertStore";
import type { ApprovalWorkflow } from "@/controllers/API/queries/prompt-library/types";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

// Single stage approval workflow config (default for all new prompts)
const SINGLE_STAGE_WORKFLOW: ApprovalWorkflow = {
  name: "Single Stage Approval",
  num_of_stages: 1,
  stages: [{ name: "STAGE_1", role: "approver" }],
};

// Commented out - for future use when approval workflow selection is enabled
// const WORKFLOW_OPTIONS = [
//   { value: "single", label: "Single Stage Approval" },
//   { value: "two_stage", label: "Two Stage Approval" },
// ];
// const WORKFLOW_CONFIGS: Record<string, ApprovalWorkflow> = {
//   direct: { name: "Direct Publishing", num_of_stages: 0, stages: [] },
//   single: { name: "Single Stage Approval", num_of_stages: 1, stages: [{ name: "STAGE_1", role: "approver" }] },
//   two_stage: { name: "Two Stage Approval", num_of_stages: 2, stages: [{ name: "STAGE_1", role: "approver" }, { name: "STAGE_2", role: "approver" }] },
// };

interface CreatePromptModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  onSuccess?: (promptId: string) => void;
}

export default function CreatePromptModal({
  open,
  setOpen,
  onSuccess,
}: CreatePromptModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [applicationId, setApplicationId] = useState("");
  const [usecaseId, setUsecaseId] = useState("");
  // Approval workflow is fixed to "single" for now
  const approvalWorkflow = "single";

  const { mutate: createPrompt, isPending } = useCreatePrompt();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setName("");
      setDescription("");
      setTags("");
      setApplicationId("");
      setUsecaseId("");
    }
  }, [open]);

  const handleSubmit = () => {
    if (!name.trim()) {
      setErrorData({
        title: "Validation Error",
        list: ["Prompt name is required"],
      });
      return;
    }

    const tagsArray = tags
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    createPrompt(
      {
        name: name.trim(),
        description: description.trim() || undefined,
        tags: tagsArray.length > 0 ? tagsArray : undefined,
        application_id: applicationId.trim() || undefined,
        usecase_id: usecaseId.trim() || undefined,
        approval_workflow: SINGLE_STAGE_WORKFLOW,
        message_chain: [{ role: "system", content: "", order: 0 }],
      },
      {
        onSuccess: (data) => {
          setSuccessData({
            title: "Prompt created successfully!",
          });
          setOpen(false);
          onSuccess?.(data.prompt_id);
        },
        onError: (error: any) => {
          setErrorData({
            title: "Failed to create prompt",
            list: [error?.response?.data?.detail || error.message || "Unknown error"],
          });
        },
      }
    );
  };

  return (
    <BaseModal open={open} setOpen={setOpen} size="small-h-full" className="h-[80vh]">
      <BaseModal.Header description="Create a new prompt template in the Prompt Library">
        <div className="flex items-center gap-2">
          <ForwardedIconComponent name="Plus" className="h-5 w-5" />
          <span>Create New Prompt</span>
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex flex-col gap-4">
          <div className="space-y-2">
            <Label htmlFor="prompt-name">
              Prompt Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="prompt-name"
              placeholder="Enter prompt name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              data-testid="input-prompt-name"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="prompt-tags">Tags (comma-separated)</Label>
            <Input
              id="prompt-tags"
              placeholder="e.g., creative, summarization, analysis"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              data-testid="input-prompt-tags"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="prompt-description">Description</Label>
            <Textarea
              id="prompt-description"
              placeholder="Describe what this prompt does"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              data-testid="input-prompt-description"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="application-id">Application ID</Label>
            <Input
              id="application-id"
              placeholder="Enter application identifier"
              value={applicationId}
              onChange={(e) => setApplicationId(e.target.value)}
              data-testid="input-application-id"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="usecase-id">Use Case ID</Label>
            <Input
              id="usecase-id"
              placeholder="Enter use case identifier"
              value={usecaseId}
              onChange={(e) => setUsecaseId(e.target.value)}
              data-testid="input-usecase-id"
            />
          </div>

          {/* Approval Workflow - Hidden for now, defaulting to single stage approval */}
          {/* <div className="space-y-2">
            <Label htmlFor="approval-workflow">Approval Workflow</Label>
            <Select value={approvalWorkflow} onValueChange={setApprovalWorkflow}>
              <SelectTrigger id="approval-workflow" data-testid="select-approval-workflow">
                <SelectValue placeholder="Select approval workflow" />
              </SelectTrigger>
              <SelectContent>
                {WORKFLOW_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Determines how many approval stages are required before publishing
            </p>
          </div> */}
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: "Create Prompt",
          loading: isPending,
          disabled: !name.trim(),
          dataTestId: "btn-create-prompt",
          onClick: handleSubmit,
        }}
      />
    </BaseModal>
  );
}
