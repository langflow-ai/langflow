import { useState } from "react";
import { Button } from "@/components/ui/button";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import CreatePromptModal from "@/modals/createPromptModal";

interface GenesisPromptWrapperProps {
  children: React.ReactNode;
  nodeId: string;
  onPromptCreated?: (promptId: string) => void;
}

/**
 * Wrapper component for Genesis Prompt Template that adds a "Create new Prompt" button
 */
export function GenesisPromptWrapper({
  children,
  nodeId,
  onPromptCreated,
}: GenesisPromptWrapperProps) {
  const [showCreateModal, setShowCreateModal] = useState(false);

  const handlePromptCreated = (promptId: string) => {
    onPromptCreated?.(promptId);
    // The dropdown should refresh automatically via the refresh button
  };

  return (
    <div className="flex flex-col gap-2 w-full">
      <div className="flex justify-end">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowCreateModal(true)}
          className="gap-1 text-xs"
          data-testid="btn-create-new-prompt"
        >
          <ForwardedIconComponent name="Plus" className="h-3 w-3" />
          Create new Prompt
        </Button>
      </div>
      {children}
      <CreatePromptModal
        open={showCreateModal}
        setOpen={setShowCreateModal}
        onSuccess={handlePromptCreated}
      />
    </div>
  );
}

export default GenesisPromptWrapper;
