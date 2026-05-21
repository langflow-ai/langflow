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

export type MemoryActionMutation = {
  mutate: (args: { memoryId: string }) => void;
  isPending: boolean;
};

export type NextIsActive = boolean | ((prevIsActive: boolean) => boolean);

export type MemoryDetailsProps = {
  memory: MemoryInfo;
  docsData?: {
    total?: number;
    sessions?: string[];
    documents?: MemoryDocumentItem[];
  };
  docsLoading: boolean;
  fetchNextMessagesPage: () => void;
  hasNextMessagesPage?: boolean;
  isFetchingNextMessagesPage?: boolean;
  selectedSession: string | null;
  setSelectedSession: (value: string | null) => void;
  groupedBySession: Map<string, MemoryDocumentItem[]>;
  handleOpenDocumentPanel: (doc: MemoryDocumentItem) => void;
  deleteMutation: MemoryActionMutation;
  handleToggleActive: (nextIsActive: NextIsActive) => void;
  onRefresh: () => Promise<void>;
  fetchNextSessionsPage: () => void;
  hasNextSessionsPage?: boolean;
  isFetchingNextSessionsPage?: boolean;
};

export type MemoriesSidebarProps = {
  filteredMemories: MemoryInfo[];
  memoriesSearch: string;
  setMemoriesSearch: (value: string) => void;
  fetchNextPage?: () => void;
  hasNextPage?: boolean;
  isFetchingNextPage?: boolean;
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
  fetchNextMessagesPage: () => void;
  hasNextMessagesPage?: boolean;
  isFetchingNextMessagesPage?: boolean;
  groupedBySession: Map<string, MemoryDocumentItem[]>;
  handleOpenDocumentPanel: (doc: MemoryDocumentItem) => void;
};

export type MemoryDetailsHeaderProps = {
  memory: MemoryInfo;
  sessions?: string[];
  selectedSession: string | null;
  setSelectedSession: (value: string | null) => void;
  deleteMutation: MemoryActionMutation;
  handleToggleActive: (nextIsActive: NextIsActive) => void;
  onRefresh: () => Promise<void>;
  fetchNextSessionsPage: () => void;
  hasNextSessionsPage?: boolean;
  isFetchingNextSessionsPage?: boolean;
};
