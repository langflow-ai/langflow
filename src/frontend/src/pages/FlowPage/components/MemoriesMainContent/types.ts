import type {
  MemoryDocumentItem,
  MemoryInfo,
} from "@/controllers/API/queries/memories/types";

export type SummaryCardProps = {
  label: string;
  value: string | number;
  icon: string;
};

export interface UseMemoriesDataProps {
  currentFlowId?: string;
  selectedMemoryId?: string | null;
  onSelectMemory?: (id: string | null) => void;
}

export interface MemoriesMainContentProps {
  selectedMemoryId?: string | null;
  onSelectMemory?: (id: string | null) => void;
}

export type MemoryActionMutation = {
  mutate: (args: { memoryId: string }) => void;
  isPending: boolean;
};

export type MemoryDetailsProps = {
  memory: MemoryInfo;
  docsData?: {
    total?: number;
    sessions?: string[];
    documents?: MemoryDocumentItem[];
  };
  docsLoading: boolean;
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  activeSearch: string;
  setActiveSearch: (value: string) => void;
  selectedSession: string | null;
  setSelectedSession: (value: string | null) => void;
  handleSearch: () => void;
  groupedBySession: Map<string, MemoryDocumentItem[]>;
  handleOpenDocumentPanel: (doc: MemoryDocumentItem) => void;
  deleteMutation: MemoryActionMutation;
  updateMemoryMutation: { isPending: boolean };
  handleToggleActive: () => void;
};

export type MemoriesSidebarProps = {
  memories?: MemoryInfo[];
  filteredMemories: MemoryInfo[];
  memoriesSearch: string;
  setMemoriesSearch: (value: string) => void;
  selectedMemoryId?: string | null;
  currentFlowId?: string;
  onSelectMemory?: (id: string | null) => void;
  onCreateMemory: () => void;
};

export type MemoryDocumentPanelProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedDocument: MemoryDocumentItem | null;
};

export type MemoryKnowledgeBaseSectionProps = {
  docsData?: {
    total?: number;
    sessions?: string[];
    documents?: MemoryDocumentItem[];
  };
  docsLoading: boolean;
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  activeSearch: string;
  setActiveSearch: (value: string) => void;
  selectedSession: string | null;
  setSelectedSession: (value: string | null) => void;
  handleSearch: () => void;
  groupedBySession: Map<string, MemoryDocumentItem[]>;
  handleOpenDocumentPanel: (doc: MemoryDocumentItem) => void;
  totalChunks: number;
};

export type MemoryStatusBannersProps = {
  memory: MemoryInfo;
  isProcessing: boolean;
};

export type MemoryDetailsHeaderProps = {
  memory: MemoryInfo;
  isProcessing: boolean;
  deleteMutation: MemoryActionMutation;
  updateMemoryMutation: { isPending: boolean };
  handleToggleActive: () => void;
};
