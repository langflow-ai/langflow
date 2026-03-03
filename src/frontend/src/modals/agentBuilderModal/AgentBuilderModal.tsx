import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useGetAgentTools } from "@/controllers/API/queries/agents";
import type {
  AgentBuilderModalProps,
  AgentFormData,
} from "./agent-builder-modal-types";
import { ToolSelector } from "./ToolSelector";

const DEFAULT_SYSTEM_PROMPT =
  "You are a helpful assistant that can use tools to answer questions and perform tasks.";

export function AgentBuilderModal({
  isOpen,
  onClose,
  onSave,
  initialData,
  isEditing = false,
}: AgentBuilderModalProps) {
  const [name, setName] = useState(initialData?.name ?? "");
  const [description, setDescription] = useState(
    initialData?.description ?? "",
  );
  const [systemPrompt, setSystemPrompt] = useState(
    initialData?.systemPrompt ?? DEFAULT_SYSTEM_PROMPT,
  );
  const [selectedTools, setSelectedTools] = useState<string[]>(
    initialData?.selectedTools ?? [],
  );
  const [toolSearch, setToolSearch] = useState("");

  const { data: tools = [] } = useGetAgentTools({});

  const handleToggleTool = useCallback((className: string) => {
    setSelectedTools((prev) =>
      prev.includes(className)
        ? prev.filter((t) => t !== className)
        : [...prev, className],
    );
  }, []);

  const handleSubmit = useCallback(() => {
    if (!name.trim()) return;

    const formData: AgentFormData = {
      name: name.trim(),
      description: description.trim(),
      systemPrompt,
      selectedTools,
    };
    onSave(formData);
  }, [name, description, systemPrompt, selectedTools, onSave]);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg" data-testid="agent-builder-modal">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Edit Agent" : "Create Agent"}
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="agent-name">Name</Label>
            <Input
              id="agent-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Agent"
              data-testid="agent-name-input"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="agent-description">Description (optional)</Label>
            <Input
              id="agent-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="A brief description of what this agent does"
              data-testid="agent-description-input"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="agent-prompt">System Prompt</Label>
            <Textarea
              id="agent-prompt"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              className="min-h-[80px]"
              data-testid="agent-prompt-input"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Tools</Label>
            <ToolSelector
              tools={tools}
              selectedTools={selectedTools}
              onToggleTool={handleToggleTool}
              searchQuery={toolSearch}
              onSearchChange={setToolSearch}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!name.trim()}
            data-testid="save-agent-button"
          >
            {isEditing ? "Save" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
