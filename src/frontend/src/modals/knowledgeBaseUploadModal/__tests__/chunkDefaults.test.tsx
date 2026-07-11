import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { BrowserRouter } from "react-router-dom";

// ── Mocks (must precede component imports) ────────────────────────────────────

const mockMutateAsync = jest.fn();
jest.mock(
  "@/controllers/API/queries/knowledge-bases/use-create-knowledge-base",
  () => ({
    useCreateKnowledgeBase: () => ({
      mutateAsync: mockMutateAsync,
      isLoading: false,
    }),
  }),
);

jest.mock(
  "@/controllers/API/queries/knowledge-bases/use-get-ingestion-job-status",
  () => ({ useGetIngestionJobStatus: () => ({ data: null }) }),
);

jest.mock(
  "@/controllers/API/queries/knowledge-bases/use-get-ingestion-runs",
  () => ({
    useGetIngestionRuns: () => ({
      data: { runs: [], total: 0, page: 1, limit: 10, total_pages: 0 },
      isLoading: false,
      isError: false,
    }),
  }),
);

jest.mock("@/controllers/API/api", () => ({
  api: { post: jest.fn(), get: jest.fn() },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/knowledge_bases"),
}));

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: () => ({
    data: [
      {
        provider: "OpenAI",
        is_enabled: true,
        icon: "OpenAI",
        models: [
          {
            model_name: "text-embedding-3-small",
            metadata: { model_type: "embeddings" },
          },
        ],
      },
    ],
    isLoading: false,
  }),
}));

jest.mock("@/stores/alertStore", () => {
  const store = jest.fn((selector) => {
    const state = {
      setSuccessData: jest.fn(),
      setErrorData: jest.fn(),
    };
    return typeof selector === "function" ? selector(state) : state;
  });
  return { __esModule: true, default: store };
});

interface MockModelInputProps {
  value: { id: string; name: string }[];
  handleOnNewValue: (val: { value: { id: string; name: string }[] }) => void;
  options: { id: string; name: string }[];
  placeholder?: string;
}

jest.mock(
  "@/components/core/parameterRenderComponent/components/modelInputComponent",
  () => ({
    __esModule: true,
    default: ({
      value,
      handleOnNewValue,
      options,
      placeholder,
    }: MockModelInputProps) => (
      <div data-testid="mock-model-input">
        <select
          data-testid="embedding-model-select"
          value={value?.[0]?.id || ""}
          onChange={(e) => {
            const selected = options?.find((o) => o.id === e.target.value);
            if (selected) handleOnNewValue({ value: [selected] });
          }}
        >
          <option value="">{placeholder || "Select..."}</option>
          {options?.map((opt) => (
            <option key={opt.id} value={opt.id}>
              {opt.name}
            </option>
          ))}
        </select>
      </div>
    ),
  }),
);

// ── Imports after mocks ───────────────────────────────────────────────────────

import { TooltipProvider } from "@radix-ui/react-tooltip";
import { DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE } from "../constants";
import KnowledgeBaseUploadModal from "../KnowledgeBaseUploadModal";

// ── Helpers ───────────────────────────────────────────────────────────────────

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <TooltipProvider>{children}</TooltipProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

const addDummyFile = () => {
  const fileInput = document.getElementById("file-input") as HTMLInputElement;
  fireEvent.change(fileInput, {
    target: {
      files: [new File(["x"], "doc.txt", { type: "text/plain" })],
    },
  } as unknown as React.ChangeEvent<HTMLInputElement>);
};

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("chunk defaults (issue #13884)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockMutateAsync.mockResolvedValue({ id: "kb1", name: "kb1" });
  });

  it("exports DEFAULT_CHUNK_SIZE=1000 and DEFAULT_CHUNK_OVERLAP=200", () => {
    expect(DEFAULT_CHUNK_SIZE).toBe(1000);
    expect(DEFAULT_CHUNK_OVERLAP).toBe(200);
  });

  it("shows 1000 and 200 as initial values for a new knowledge base", async () => {
    render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
      wrapper: createWrapper(),
    });

    addDummyFile();

    await waitFor(() =>
      expect(screen.getByTestId("kb-chunk-size-input")).not.toBeDisabled(),
    );

    expect(screen.getByTestId("kb-chunk-size-input")).toHaveValue(1000);
    expect(screen.getByTestId("kb-chunk-overlap-input")).toHaveValue(200);
  });
});
