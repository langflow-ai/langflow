import type { AgentToolInfo } from "@/controllers/API/queries/agents";

export interface AgentFormData {
  name: string;
  description: string;
  systemPrompt: string;
  selectedTools: string[];
}

export interface AgentBuilderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: AgentFormData) => void;
  initialData?: AgentFormData;
  isEditing?: boolean;
}

export interface ToolSelectorProps {
  tools: AgentToolInfo[];
  selectedTools: string[];
  onToggleTool: (className: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}
