import { render, screen } from "@testing-library/react";
import type { MemoryInfo } from "@/controllers/API/queries/memories/types";
import type { MemoryDetailsProps } from "../../types";
import { MemoryDetails } from "../MemoryDetails";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("@/components/ui/popover", () => ({
  Popover: ({
    children,
    open,
    onOpenChange,
  }: {
    children: React.ReactNode;
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
  }) => (
    <div data-testid="popover" data-open={open}>
      {React.Children.map(children, (child) => {
        if (React.isValidElement(child)) {
          return React.cloneElement(
            child as React.ReactElement<{
              onOpenChange?: (open: boolean) => void;
            }>,
            { onOpenChange },
          );
        }
        return child;
      })}
    </div>
  ),
  PopoverTrigger: ({
    children,
    onOpenChange,
  }: {
    children: React.ReactNode;
    asChild?: boolean;
    onOpenChange?: (open: boolean) => void;
  }) => (
    <div data-testid="popover-trigger" onClick={() => onOpenChange?.(true)}>
      {children}
    </div>
  ),
  PopoverContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="popover-content">{children}</div>
  ),
}));

jest.mock("../MemoryDetailsHeader", () => ({
  MemoryDetailsHeader: () => <div data-testid="memory-details-header" />,
}));

jest.mock("../MemoryKnowledgeBaseSection", () => ({
  MemoryKnowledgeBaseSection: () => (
    <div data-testid="memory-knowledge-base-section" />
  ),
}));

jest.mock("../SummaryCard", () => ({
  SummaryCard: ({
    label,
    value,
  }: {
    label: string;
    value: string | number;
  }) => (
    <div data-testid="summary-card">
      <span data-testid="summary-card-label">{label}</span>
      <span data-testid="summary-card-value">{value}</span>
    </div>
  ),
}));

import React from "react";

const baseMemory: MemoryInfo = {
  id: "mem-1",
  name: "Test Memory",
  kb_name: "kb-1",
  embedding_model: "text-embedding-3-small",
  is_active: true,
  total_messages_processed: 10,
  sessions_count: 2,
  batch_size: 1,
  preprocessing_enabled: false,
  pending_messages_count: 0,
  user_id: "user-1",
  flow_id: "flow-1",
};

const baseProps: MemoryDetailsProps = {
  memory: baseMemory,
  docsData: undefined,
  docsLoading: false,
  fetchNextMessagesPage: jest.fn(),
  hasNextMessagesPage: false,
  isFetchingNextMessagesPage: false,
  selectedSession: null,
  setSelectedSession: jest.fn(),
  groupedBySession: new Map(),
  handleOpenDocumentPanel: jest.fn(),
  deleteMutation: {
    mutate: jest.fn(),
    isPending: false,
  } as unknown as MemoryDetailsProps["deleteMutation"],
  handleToggleActive: jest.fn(),
  onRefresh: jest.fn().mockResolvedValue(undefined),
  fetchNextSessionsPage: jest.fn(),
  hasNextSessionsPage: false,
  isFetchingNextSessionsPage: false,
};

describe("MemoryDetails — Config popover", () => {
  it("shows the embedding model name in the trigger", () => {
    render(<MemoryDetails {...baseProps} />);
    const matches = screen.getAllByText("text-embedding-3-small");
    expect(matches.length).toBeGreaterThanOrEqual(1);
    expect(matches.some((el) => el.className.includes("truncate"))).toBe(true);
  });

  it("shows model label and embedding model in the popover content", () => {
    render(<MemoryDetails {...baseProps} />);
    // t("memory.modelLabel") = "Model:"
    expect(screen.getByText("Model:")).toBeInTheDocument();
    const modelValues = screen.getAllByText("text-embedding-3-small");
    expect(
      modelValues.some((el) => el.className.includes("text-foreground")),
    ).toBe(true);
  });

  it("shows preprocessing as Disabled when preprocessing_enabled is false", () => {
    render(<MemoryDetails {...baseProps} />);
    expect(screen.getByText("Disabled")).toBeInTheDocument();
  });

  it("shows preprocessing as Enabled when preprocessing_enabled is true", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={{ ...baseMemory, preprocessing_enabled: true }}
      />,
    );
    expect(screen.getByText("Enabled")).toBeInTheDocument();
  });

  it("does not show Provider row when embedding_provider is absent", () => {
    render(<MemoryDetails {...baseProps} />);
    // t("memory.providerLabel") = "Provider:"
    expect(screen.queryByText("Provider:")).not.toBeInTheDocument();
  });

  it("shows Provider row when embedding_provider is present", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={{ ...baseMemory, embedding_provider: "OpenAI" }}
      />,
    );
    // t("memory.providerLabel") = "Provider:"
    expect(screen.getByText("Provider:")).toBeInTheDocument();
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
  });

  it("does not show Batch Size row when batch_size is 1", () => {
    render(<MemoryDetails {...baseProps} />);
    // t("memory.messagesPerBatch") = "Messages per batch:"
    expect(screen.queryByText("Messages per batch:")).not.toBeInTheDocument();
  });

  it("shows Batch Size row when batch_size > 1", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={{ ...baseMemory, batch_size: 5 }}
      />,
    );
    // t("memory.messagesPerBatch") = "Messages per batch:"
    expect(screen.getByText("Messages per batch:")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("does not show Preprocessing Model when preprocessing is disabled", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={{
          ...baseMemory,
          preprocessing_enabled: false,
          preprocessing_model: "gpt-4o-mini",
        }}
      />,
    );
    // t("memory.preprocessingModel") = "Preprocessing model:"
    expect(screen.queryByText("Preprocessing model:")).not.toBeInTheDocument();
  });

  it("shows Preprocessing Model when preprocessing is enabled and model is set", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={{
          ...baseMemory,
          preprocessing_enabled: true,
          preprocessing_model: "gpt-4o-mini",
        }}
      />,
    );
    // t("memory.preprocessingModel") = "Preprocessing model:"
    expect(screen.getByText("Preprocessing model:")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument();
  });

  it("does not show Preprocessing Instructions section when preprocessing is disabled", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={{
          ...baseMemory,
          preprocessing_enabled: false,
          preproc_instructions: "Summarise briefly.",
        }}
      />,
    );
    // t("memory.preprocessingInstructions") = "Preprocessing instructions:"
    expect(
      screen.queryByText("Preprocessing instructions:"),
    ).not.toBeInTheDocument();
  });

  it("shows Preprocessing Instructions section when preprocessing is enabled", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={{ ...baseMemory, preprocessing_enabled: true }}
      />,
    );
    expect(screen.getByText("Preprocessing instructions:")).toBeInTheDocument();
  });

  it("shows instructions value when preprocessing is enabled and instructions are set", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={{
          ...baseMemory,
          preprocessing_enabled: true,
          preproc_instructions: "Summarise briefly.",
        }}
      />,
    );
    expect(screen.getByText("Preprocessing instructions:")).toBeInTheDocument();
    expect(screen.getByText("Summarise briefly.")).toBeInTheDocument();
  });

  it("chevron icon starts without rotate-180 class", () => {
    render(<MemoryDetails {...baseProps} />);
    const chevron = screen.getByTestId("icon-ChevronDown");
    expect(chevron.className).not.toContain("rotate-180");
  });
});

describe("MemoryDetails — stat cards session filtering", () => {
  const memoryWithStats: MemoryInfo = {
    ...baseMemory,
    total_messages_processed: 42,
    pending_messages_count: 3,
    last_generated_at: "2024-06-01T12:00:00Z",
  };

  function getValueByLabel(label: string) {
    const cards = screen.getAllByTestId("summary-card");
    const card = cards.find(
      (c) =>
        c.querySelector(`[data-testid="summary-card-label"]`)?.textContent ===
        label,
    );
    return card?.querySelector(`[data-testid="summary-card-value"]`)
      ?.textContent;
  }

  it("shows — for all stat cards when selectedSession is null (All Sessions default)", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={memoryWithStats}
        selectedSession={null}
      />,
    );
    expect(getValueByLabel("Processed Messages")).toBe("—");
    expect(getValueByLabel("Pending Messages")).toBe("—");
    expect(getValueByLabel("Last Generated")).toBe("—");
  });

  it("shows — for all stat cards when selectedSession is ALL_SESSIONS_VALUE", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={memoryWithStats}
        selectedSession="__all__"
      />,
    );
    expect(getValueByLabel("Processed Messages")).toBe("—");
    expect(getValueByLabel("Pending Messages")).toBe("—");
    expect(getValueByLabel("Last Generated")).toBe("—");
  });

  it("shows actual values when a specific session is selected", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={memoryWithStats}
        selectedSession="session-abc"
      />,
    );
    expect(getValueByLabel("Processed Messages")).toBe("42");
    expect(getValueByLabel("Pending Messages")).toBe("3");
    expect(getValueByLabel("Last Generated")).not.toBe("—");
    expect(getValueByLabel("Last Generated")).not.toBe("");
  });

  it("shows 0 for Processed Messages when value is 0 and a session is selected", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={{ ...memoryWithStats, total_messages_processed: 0 }}
        selectedSession="session-abc"
      />,
    );
    expect(getValueByLabel("Processed Messages")).toBe("0");
  });

  it("shows 0 for Pending Messages when value is 0 and a session is selected", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={{ ...memoryWithStats, pending_messages_count: 0 }}
        selectedSession="session-abc"
      />,
    );
    expect(getValueByLabel("Pending Messages")).toBe("0");
  });

  it("shows Never for Last Generated when date is absent and session is selected", () => {
    render(
      <MemoryDetails
        {...baseProps}
        memory={{ ...memoryWithStats, last_generated_at: undefined }}
        selectedSession="session-abc"
      />,
    );
    expect(getValueByLabel("Last Generated")).toBe("Never");
  });
});
