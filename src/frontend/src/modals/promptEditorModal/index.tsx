import { useState, useEffect, useMemo } from "react";
import BaseModal from "../baseModal";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useCreateVersion,
  useUpdateVersion,
  useSubmitForReview,
} from "@/controllers/API/queries/prompt-library";
import useAlertStore from "@/stores/alertStore";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { PromptVersion, MessageChainItem } from "@/controllers/API/queries/prompt-library/types";

interface PromptEditorModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  promptId: string;
  promptName: string;
  existingVersion?: PromptVersion;
  isNewVersion?: boolean;
  onSuccess?: () => void;
}

export default function PromptEditorModal({
  open,
  setOpen,
  promptId,
  promptName,
  existingVersion,
  isNewVersion = false,
  onSuccess,
}: PromptEditorModalProps) {
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const [changeDescription, setChangeDescription] = useState("");

  const { mutate: createVersion, isPending: isCreating } = useCreateVersion();
  const { mutate: updateVersion, isPending: isUpdating } = useUpdateVersion();
  const { mutate: submitForReview, isPending: isSubmitting } = useSubmitForReview();

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const isPending = isCreating || isUpdating || isSubmitting;

  // Determine if we can edit (only DRAFT versions can be edited)
  const canEdit = useMemo(() => {
    if (isNewVersion) return true;
    return existingVersion?.status === "DRAFT";
  }, [existingVersion, isNewVersion]);

  const isPublished = existingVersion?.status === "PUBLISHED";
  
  // Track if content has been modified (for warning when creating new version)
  const [hasContentChanged, setHasContentChanged] = useState(false);
  const [originalSystemPrompt, setOriginalSystemPrompt] = useState("");
  const [originalUserPrompt, setOriginalUserPrompt] = useState("");

  // Initialize form from existing version
  useEffect(() => {
    if (open) {
      if (existingVersion) {
        const systemMsg = existingVersion.message_chain.find((m) => m.role === "system");
        const userMsg = existingVersion.message_chain.find((m) => m.role === "user");
        const sysContent = systemMsg?.content || "";
        const usrContent = userMsg?.content || "";
        setSystemPrompt(sysContent);
        setUserPrompt(usrContent);
        setOriginalSystemPrompt(sysContent);
        setOriginalUserPrompt(usrContent);
        setChangeDescription(isNewVersion ? "" : existingVersion.change_description || "");
        setHasContentChanged(false);
      } else {
        setSystemPrompt("");
        setUserPrompt("");
        setOriginalSystemPrompt("");
        setOriginalUserPrompt("");
        setChangeDescription("");
        setHasContentChanged(false);
      }
    }
  }, [open, existingVersion, isNewVersion]);

  // Track content changes
  useEffect(() => {
    if (existingVersion && !isNewVersion) {
      const changed = systemPrompt !== originalSystemPrompt || userPrompt !== originalUserPrompt;
      setHasContentChanged(changed);
    }
  }, [systemPrompt, userPrompt, originalSystemPrompt, originalUserPrompt, existingVersion, isNewVersion]);

  const buildMessageChain = (): MessageChainItem[] => {
    const chain: MessageChainItem[] = [];
    if (systemPrompt.trim()) {
      chain.push({ role: "system", content: systemPrompt.trim(), order: 0 });
    }
    if (userPrompt.trim()) {
      chain.push({ role: "user", content: userPrompt.trim(), order: 1 });
    }
    return chain;
  };

  const handleSaveAsDraft = () => {
    if (!systemPrompt.trim() && !userPrompt.trim()) {
      setErrorData({
        title: "Validation Error",
        list: ["At least one prompt (system or user) is required"],
      });
      return;
    }

    const messageChain = buildMessageChain();
    const description = changeDescription.trim() || "Draft version";

    if (isNewVersion || !existingVersion) {
      // Create new version
      createVersion(
        {
          promptId,
          message_chain: messageChain,
          variables: [],
          change_description: description,
        },
        {
          onSuccess: () => {
            setSuccessData({ title: "Version saved as draft!" });
            setOpen(false);
            onSuccess?.();
          },
          onError: (error: any) => {
            setErrorData({
              title: "Failed to save draft",
              list: [error?.response?.data?.detail || error.message || "Unknown error"],
            });
          },
        }
      );
    } else {
      // Update existing draft version
      updateVersion(
        {
          promptId,
          version: existingVersion.version,
          message_chain: messageChain,
          variables: existingVersion.variables || [],
          config: existingVersion.config,
          change_description: description,
        },
        {
          onSuccess: () => {
            setSuccessData({ title: "Draft updated!" });
            setOpen(false);
            onSuccess?.();
          },
          onError: (error: any) => {
            setErrorData({
              title: "Failed to update draft",
              list: [error?.response?.data?.detail || error.message || "Unknown error"],
            });
          },
        }
      );
    }
  };

  const handleSubmitForReview = () => {
    if (!systemPrompt.trim() && !userPrompt.trim()) {
      setErrorData({
        title: "Validation Error",
        list: ["At least one prompt (system or user) is required"],
      });
      return;
    }

    const messageChain = buildMessageChain();
    const description = changeDescription.trim() || "Submitted for review";

    const submitVersion = (versionNum: number) => {
      submitForReview(
        {
          promptId,
          version: versionNum,
        },
        {
          onSuccess: () => {
            setSuccessData({ title: "Version submitted for review!" });
            setOpen(false);
            onSuccess?.();
          },
          onError: (error: any) => {
            setErrorData({
              title: "Failed to submit for review",
              list: [error?.response?.data?.detail || error.message || "Unknown error"],
            });
          },
        }
      );
    };

    if (isNewVersion || !existingVersion) {
      // Create new version first, then submit
      createVersion(
        {
          promptId,
          message_chain: messageChain,
          variables: [],
          change_description: description,
        },
        {
          onSuccess: (data) => {
            submitVersion(data.version);
          },
          onError: (error: any) => {
            setErrorData({
              title: "Failed to create version",
              list: [error?.response?.data?.detail || error.message || "Unknown error"],
            });
          },
        }
      );
    } else if (existingVersion.status === "DRAFT") {
      // Update draft first, then submit
      updateVersion(
        {
          promptId,
          version: existingVersion.version,
          message_chain: messageChain,
          variables: existingVersion.variables || [],
          config: existingVersion.config,
          change_description: description,
        },
        {
          onSuccess: () => {
            submitVersion(existingVersion.version);
          },
          onError: (error: any) => {
            setErrorData({
              title: "Failed to update version",
              list: [error?.response?.data?.detail || error.message || "Unknown error"],
            });
          },
        }
      );
    }
  };

  return (
    <BaseModal open={open} setOpen={setOpen} size="x-large">
      <BaseModal.Header
        description={
          isNewVersion
            ? "Create a new version of this prompt"
            : canEdit
              ? "Edit the prompt content"
              : "View prompt content (read-only)"
        }
      >
        <div className="flex items-center gap-2">
          <ForwardedIconComponent name="TerminalSquare" className="h-5 w-5" />
          <span>{promptName}</span>
          {existingVersion && (
            <span className="text-sm text-muted-foreground">
              v{existingVersion.version}
              {existingVersion.status !== "PUBLISHED" && ` [${existingVersion.status}]`}
            </span>
          )}
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex flex-col gap-4 h-full">
          <div className="space-y-2 flex-1">
            <Label htmlFor="system-prompt">System Prompt</Label>
            <Textarea
              id="system-prompt"
              placeholder="Enter system prompt content..."
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              className="min-h-[150px] resize-none"
              disabled={!canEdit}
              data-testid="textarea-system-prompt"
            />
            <p className="text-xs text-muted-foreground">
              Use {"{{variable_name}}"} syntax for dynamic variables
            </p>
          </div>

          <div className="space-y-2 flex-1">
            <Label htmlFor="user-prompt">User Prompt (Optional)</Label>
            <Textarea
              id="user-prompt"
              placeholder="Enter user prompt content..."
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              className="min-h-[100px] resize-none"
              disabled={!canEdit}
              data-testid="textarea-user-prompt"
            />
          </div>

          {canEdit && (
            <div className="space-y-2">
              <Label htmlFor="change-description">Change Description</Label>
              <Textarea
                id="change-description"
                placeholder="Describe what changed in this version..."
                value={changeDescription}
                onChange={(e) => setChangeDescription(e.target.value)}
                rows={2}
                data-testid="textarea-change-description"
              />
            </div>
          )}

          {isPublished && (
            <div className="rounded-md bg-muted p-3 text-sm">
              <p className="font-medium">This is a published version</p>
              <p className="text-muted-foreground">
                To make changes, a new version will be created.
              </p>
            </div>
          )}

          {hasContentChanged && !isNewVersion && existingVersion?.status === "PUBLISHED" && (
            <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-sm">
              <p className="font-medium text-amber-800">⚠️ Content Modified</p>
              <p className="text-amber-700">
                You have modified the prompt content. A new version will be created when you click "Save as Draft" or "Submit for Review".
              </p>
            </div>
          )}

          {isNewVersion && (
            <div className="rounded-md bg-blue-50 border border-blue-200 p-3 text-sm">
              <p className="font-medium text-blue-800">Creating New Version</p>
              <p className="text-blue-700">
                This will create a new version of the prompt that follows the assigned approval workflow.
              </p>
            </div>
          )}
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full items-center justify-end gap-3">
          <Button variant="outline" onClick={() => setOpen(false)} disabled={isPending}>
            Cancel
          </Button>
          {canEdit && (
            <>
              <Button
                variant="outline"
                onClick={handleSaveAsDraft}
                disabled={isPending || (!systemPrompt.trim() && !userPrompt.trim())}
                data-testid="btn-save-draft"
              >
                {isPending ? "Saving..." : "Save as Draft"}
              </Button>
              <Button
                onClick={handleSubmitForReview}
                disabled={isPending || (!systemPrompt.trim() && !userPrompt.trim())}
                data-testid="btn-submit-review"
              >
                {isPending ? "Submitting..." : "Submit for Review"}
              </Button>
            </>
          )}
          {isPublished && (
            <Button
              onClick={() => {
                // Trigger new version creation mode
                setOpen(false);
                // Parent should handle opening with isNewVersion=true
              }}
              data-testid="btn-create-new-version"
            >
              Create New Version
            </Button>
          )}
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
