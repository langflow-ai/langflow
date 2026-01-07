import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { BrowserRouter } from "react-router-dom";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";

/**
 * Creates a test wrapper with React Query and Router providers
 */
export const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

/**
 * Mock knowledge base data for testing
 */
export const mockKnowledgeBase: KnowledgeBaseInfo = {
  id: "kb-1",
  name: "Test Knowledge Base",
  embedding_provider: "OpenAI",
  embedding_model: "text-embedding-ada-002",
  size: 1024000,
  words: 50000,
  characters: 250000,
  chunks: 100,
  avg_chunk_size: 2500,
};

export const mockKnowledgeBaseList: KnowledgeBaseInfo[] = [
  mockKnowledgeBase,
  {
    id: "kb-2",
    name: "Second Knowledge Base",
    embedding_provider: "Anthropic",
    embedding_model: "claude-embedding",
    size: 2048000,
    words: 75000,
    characters: 400000,
    chunks: 150,
    avg_chunk_size: 2666,
  },
  {
    id: "kb-3",
    name: "Third Knowledge Base",
    embedding_model: undefined, // Test case for missing embedding model
    size: 512000,
    words: 25000,
    characters: 125000,
    chunks: 50,
    avg_chunk_size: 2500,
  },
];

/**
 * Mock ForwardedIconComponent for consistent testing
 */
export const mockIconComponent = () => {
  jest.mock("@/components/common/genericIconComponent", () => {
    const MockedIcon = ({
      name,
      ...props
    }: {
      name: string;
      [key: string]: any;
    }) => <span data-testid={`icon-${name}`} {...props} />;
    MockedIcon.displayName = "ForwardedIconComponent";
    return MockedIcon;
  });
};

/**
 * Mock TableComponent for testing components that use ag-grid
 */
export const mockTableComponent = () => {
  jest.mock(
    "@/components/core/parameterRenderComponent/components/tableComponent",
    () => {
      const MockTable = (props: any) => (
        <div data-testid="mock-table" {...props}>
          <div data-testid="table-content">Mock Table</div>
        </div>
      );
      MockTable.displayName = "TableComponent";
      return MockTable;
    },
  );
};

/**
 * Common alert store mock setup
 */
export const setupAlertStoreMock = () => {
  const mockSetSuccessData = jest.fn();
  const mockSetErrorData = jest.fn();

  return {
    mockSetSuccessData,
    mockSetErrorData,
    mockAlertStore: {
      setSuccessData: mockSetSuccessData,
      setErrorData: mockSetErrorData,
    },
  };
};

/**
 * Mock react-router-dom useParams hook
 */
export const mockUseParams = (
  params: Record<string, string | undefined> = {},
) => {
  jest.doMock("react-router-dom", () => ({
    ...jest.requireActual("react-router-dom"),
    useParams: () => params,
  }));
};
