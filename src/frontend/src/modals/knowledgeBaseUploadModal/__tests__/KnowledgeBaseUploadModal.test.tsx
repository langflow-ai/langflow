import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { BrowserRouter } from "react-router-dom";

// ── Mocks (must precede component imports) ──────────────────────────────────

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
  () => ({
    useGetIngestionJobStatus: () => ({ data: null }),
  }),
);

const mockApiPost = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { post: mockApiPost, get: jest.fn() },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/knowledge_bases"),
}));

const MODEL_PROVIDERS = [
  {
    provider: "OpenAI",
    is_enabled: true,
    icon: "OpenAI",
    models: [
      {
        model_name: "text-embedding-3-small",
        metadata: { model_type: "embeddings" },
      },
      {
        model_name: "text-embedding-3-large",
        metadata: { model_type: "embeddings" },
      },
      { model_name: "gpt-4", metadata: { model_type: "llm" } },
    ],
  },
  {
    provider: "HuggingFace",
    is_enabled: true,
    icon: "HuggingFace",
    models: [
      {
        model_name: "sentence-transformers/all-MiniLM-L6-v2",
        metadata: { model_type: "embeddings" },
      },
    ],
  },
  {
    provider: "DisabledProvider",
    is_enabled: false,
    icon: "Bot",
    models: [
      {
        model_name: "disabled-embedding",
        metadata: { model_type: "embeddings" },
      },
    ],
  },
];

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: () => ({ data: MODEL_PROVIDERS, isLoading: false }),
}));

const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();
jest.mock("@/stores/alertStore", () => {
  const store = jest.fn((selector) => {
    const state = {
      setSuccessData: mockSetSuccessData,
      setErrorData: mockSetErrorData,
    };
    return typeof selector === "function" ? selector(state) : state;
  });
  return { __esModule: true, default: store };
});

// Renders as a plain <select> so tests can inspect options and fire selections
jest.mock(
  "@/components/core/parameterRenderComponent/components/modelInputComponent",
  () => ({
    __esModule: true,
    default: ({ value, handleOnNewValue, options, placeholder }: any) => (
      <div data-testid="mock-model-input">
        <select
          data-testid="embedding-model-select"
          value={value?.[0]?.id || ""}
          onChange={(e) => {
            const selected = options?.find((o: any) => o.id === e.target.value);
            if (selected) handleOnNewValue({ value: [selected] });
          }}
        >
          <option value="">{placeholder || "Select..."}</option>
          {options?.map((opt: any) => (
            <option key={opt.id} value={opt.id}>
              {opt.name}
            </option>
          ))}
        </select>
      </div>
    ),
  }),
);

// ── Imports after mocks ──────────────────────────────────────────────────────

import { TooltipProvider } from "@radix-ui/react-tooltip";
import KnowledgeBaseUploadModal from "../KnowledgeBaseUploadModal";

// ── Utilities ────────────────────────────────────────────────────────────────

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

/** Types name and selects an embedding model — prerequisite for most flow tests. */
const fillRequiredFields = async (
  user: ReturnType<typeof userEvent.setup>,
  name = "TestKnowledgeBase",
) => {
  await user.type(screen.getByTestId("kb-source-name-input"), name);
  await user.selectOptions(
    screen.getByTestId("embedding-model-select"),
    "text-embedding-3-small",
  );
};

// ── Tests ────────────────────────────────────────────────────────────────────

describe("KnowledgeBaseUploadModal", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockMutateAsync.mockResolvedValue({ id: "test_kb", name: "test_kb" });
    mockApiPost.mockResolvedValue({ data: { files: [] } });
  });

  // ── Rendering ─────────────────────────────────────────────────────────────

  describe("Rendering", () => {
    it("renders modal when open", () => {
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      expect(screen.getByText("Create Knowledge Base")).toBeInTheDocument();
    });

    it("does not render modal content when closed", () => {
      render(<KnowledgeBaseUploadModal open={false} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      expect(
        screen.queryByText("Create Knowledge Base"),
      ).not.toBeInTheDocument();
    });

    it("renders source name input", () => {
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      expect(screen.getByTestId("kb-source-name-input")).toBeInTheDocument();
    });

    it("renders embedding model label", () => {
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      expect(screen.getByText("Embedding Model")).toBeInTheDocument();
    });

    it("renders Configure Sources toggle button in footer", () => {
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      expect(
        screen.getByRole("button", { name: /Configure Sources/i }),
      ).toBeInTheDocument();
    });

    it('shows "Add Sources" title in add-sources mode', async () => {
      render(
        <KnowledgeBaseUploadModal
          open={true}
          setOpen={jest.fn()}
          existingKnowledgeBase={{ name: "ExistingKB" }}
        />,
        { wrapper: createWrapper() },
      );
      await waitFor(() =>
        expect(
          screen.getByRole("heading", { name: /Add Sources/i }),
        ).toBeInTheDocument(),
      );
    });
  });

  // ── Embedding Model Filtering ──────────────────────────────────────────────

  describe("Embedding Model Filtering", () => {
    it("includes only embeddings-type models in the select options", () => {
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      const optionValues = Array.from(
        screen.getByTestId("embedding-model-select").querySelectorAll("option"),
      ).map((o) => (o as HTMLOptionElement).value);

      expect(optionValues).toContain("text-embedding-3-small");
      expect(optionValues).toContain("text-embedding-3-large");
      expect(optionValues).toContain("sentence-transformers/all-MiniLM-L6-v2");
    });

    it("excludes LLM-type models (gpt-4) from embedding options", () => {
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      const optionValues = Array.from(
        screen.getByTestId("embedding-model-select").querySelectorAll("option"),
      ).map((o) => (o as HTMLOptionElement).value);

      expect(optionValues).not.toContain("gpt-4");
    });

    it("excludes models from disabled providers", () => {
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      const optionValues = Array.from(
        screen.getByTestId("embedding-model-select").querySelectorAll("option"),
      ).map((o) => (o as HTMLOptionElement).value);

      expect(optionValues).not.toContain("disabled-embedding");
    });
  });

  // ── Form Validation ────────────────────────────────────────────────────────

  describe("Form Validation", () => {
    it("submit button is disabled when form is empty", () => {
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      expect(screen.getByTestId("kb-create-button")).toBeDisabled();
    });

    it("submit button is disabled when only source name is filled", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      await user.type(
        screen.getByTestId("kb-source-name-input"),
        "MyKnowledgeBase",
      );
      expect(screen.getByTestId("kb-create-button")).toBeDisabled();
    });

    it("submit button is enabled when name and embedding model are both provided", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      await fillRequiredFields(user);
      expect(screen.getByTestId("kb-create-button")).not.toBeDisabled();
    });

    it("shows inline error when name is shorter than 3 characters", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      await user.type(screen.getByTestId("kb-source-name-input"), "ab");
      await user.selectOptions(
        screen.getByTestId("embedding-model-select"),
        "text-embedding-3-small",
      );
      await user.click(screen.getByTestId("kb-create-button"));
      await waitFor(() =>
        expect(
          screen.getByText("Name must be between 3 and 512 characters"),
        ).toBeInTheDocument(),
      );
    });

    it("shows inline error when name contains invalid characters", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      await user.type(screen.getByTestId("kb-source-name-input"), "invalid!");
      await user.selectOptions(
        screen.getByTestId("embedding-model-select"),
        "text-embedding-3-small",
      );
      await user.click(screen.getByTestId("kb-create-button"));
      await waitFor(() =>
        expect(screen.getByText(/Name must only contain/)).toBeInTheDocument(),
      );
    });

    it("shows inline error when name duplicates an existing knowledge base", async () => {
      const user = userEvent.setup();
      render(
        <KnowledgeBaseUploadModal
          open={true}
          setOpen={jest.fn()}
          existingKnowledgeBaseNames={["TestKnowledgeBase"]}
        />,
        { wrapper: createWrapper() },
      );
      await fillRequiredFields(user);
      await user.click(screen.getByTestId("kb-create-button"));
      await waitFor(() =>
        expect(
          screen.getByText("A knowledge base with this name already exists"),
        ).toBeInTheDocument(),
      );
    });
  });

  // ── Form Submission ────────────────────────────────────────────────────────

  describe("Form Submission", () => {
    it("calls mutateAsync with correct payload on valid submission", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      await fillRequiredFields(user);
      await user.click(screen.getByTestId("kb-create-button"));
      await waitFor(() =>
        expect(mockMutateAsync).toHaveBeenCalledWith({
          name: "TestKnowledgeBase",
          embedding_provider: "OpenAI",
          embedding_model: "text-embedding-3-small",
          column_config: [
            { column_name: "text", vectorize: true, identifier: true },
          ],
        }),
      );
    });

    it("calls setSuccessData with the knowledge base name after creation", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      await fillRequiredFields(user);
      await user.click(screen.getByTestId("kb-create-button"));
      await waitFor(() =>
        expect(mockSetSuccessData).toHaveBeenCalledWith({
          title: 'Knowledge base "TestKnowledgeBase" created',
        }),
      );
    });

    it("calls setOpen(false) after successful submission", async () => {
      const mockSetOpen = jest.fn();
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={mockSetOpen} />, {
        wrapper: createWrapper(),
      });
      await fillRequiredFields(user);
      await user.click(screen.getByTestId("kb-create-button"));
      await waitFor(() => expect(mockSetOpen).toHaveBeenCalledWith(false));
    });

    it("fires onSubmit callback with source name and files after creation", async () => {
      const mockOnSubmit = jest.fn();
      const user = userEvent.setup();
      render(
        <KnowledgeBaseUploadModal
          open={true}
          setOpen={jest.fn()}
          onSubmit={mockOnSubmit}
        />,
        { wrapper: createWrapper() },
      );
      await fillRequiredFields(user);
      await user.click(screen.getByTestId("kb-create-button"));
      await waitFor(() => expect(mockOnSubmit).toHaveBeenCalled());
      expect(mockOnSubmit.mock.calls[0][0]).toMatchObject({
        sourceName: "TestKnowledgeBase",
        files: [],
      });
    });

    it("calls setErrorData when the creation API returns an error", async () => {
      mockMutateAsync.mockRejectedValueOnce({
        response: { data: { detail: "Knowledge base already exists" } },
      });
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      await fillRequiredFields(user);
      await user.click(screen.getByTestId("kb-create-button"));
      await waitFor(() =>
        expect(mockSetErrorData).toHaveBeenCalledWith({
          title: "Knowledge base already exists",
        }),
      );
    });
  });

  // ── User Interactions ──────────────────────────────────────────────────────

  describe("User Interactions", () => {
    it("allows typing in the source name input", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      const input = screen.getByTestId("kb-source-name-input");
      await user.type(input, "My Knowledge Base");
      expect(input).toHaveValue("My Knowledge Base");
    });

    it("clears source name when the input is cleared", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      const input = screen.getByTestId("kb-source-name-input");
      await user.type(input, "Test");
      await user.clear(input);
      expect(input).toHaveValue("");
    });

    it("opens file-upload dropdown when Add Sources button is clicked", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      await user.click(
        screen.getByRole("button", { name: /Configure Sources/i }),
      );
      await user.click(screen.getByTestId("kb-browse-btn"));
      expect(screen.getByText("Upload Files")).toBeInTheDocument();
      expect(screen.getByText("Upload Folder")).toBeInTheDocument();
    });
  });

  // ── File Upload ────────────────────────────────────────────────────────────

  describe("File Upload", () => {
    it("adds an uploaded file to the files panel", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      const fileInput = document.getElementById(
        "file-input",
      ) as HTMLInputElement;
      await user.upload(
        fileInput,
        new File(["content"], "document.txt", { type: "text/plain" }),
      );
      expect(screen.getByText("document.txt")).toBeInTheDocument();
    });

    it("shows all uploaded files when multiple files are selected", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      const fileInput = document.getElementById(
        "file-input",
      ) as HTMLInputElement;
      await user.upload(fileInput, [
        new File(["a"], "file-a.txt", { type: "text/plain" }),
        new File(["b"], "file-b.txt", { type: "text/plain" }),
      ]);
      expect(screen.getByText("file-a.txt")).toBeInTheDocument();
      expect(screen.getByText("file-b.txt")).toBeInTheDocument();
    });
  });

  // ── Step 2 Review ──────────────────────────────────────────────────────────

  describe("Step 2 Review", () => {
    const navigateToStep2 = async (
      user: ReturnType<typeof userEvent.setup>,
      name = "TestKnowledgeBase",
    ) => {
      await fillRequiredFields(user, name);
      await user.click(
        screen.getByRole("button", { name: /Configure Sources/i }),
      );
      await user.click(screen.getByRole("button", { name: /Next Step/i }));
    };

    it("transitions to the Review & Build step after clicking Next Step", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      await navigateToStep2(user);
      expect(screen.getByText("Review & Build")).toBeInTheDocument();
    });

    it('shows "No files selected" message in review when no files were uploaded', async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      await navigateToStep2(user);
      expect(
        screen.getByText("No files selected. Go back to add files."),
      ).toBeInTheDocument();
    });

    it("shows the source name in the review summary", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      await navigateToStep2(user, "MyDocuments");
      expect(screen.getAllByText("MyDocuments").length).toBeGreaterThan(0);
    });

    it("returns to step 1 when Back is clicked in the review step", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      await navigateToStep2(user);
      await user.click(screen.getByRole("button", { name: /Back/i }));
      expect(screen.getByText("Create Knowledge Base")).toBeInTheDocument();
      expect(screen.queryByText("Review & Build")).not.toBeInTheDocument();
    });

    it("calls the chunk preview API when entering review step with uploaded files", async () => {
      const user = userEvent.setup();
      mockApiPost.mockResolvedValue({
        data: {
          files: [
            {
              preview_chunks: [
                { content: "preview chunk", char_count: 13, start: 0, end: 13 },
              ],
            },
          ],
        },
      });
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      const fileInput = document.getElementById(
        "file-input",
      ) as HTMLInputElement;
      await user.upload(
        fileInput,
        new File(["hello world"], "test.txt", { type: "text/plain" }),
      );
      await navigateToStep2(user);
      await waitFor(() =>
        expect(mockApiPost).toHaveBeenCalledWith(
          expect.stringContaining("preview-chunks"),
          expect.any(FormData),
          expect.objectContaining({
            headers: { "Content-Type": "multipart/form-data" },
          }),
        ),
      );
    });

    it("renders chunk content returned by the preview API", async () => {
      const user = userEvent.setup();
      mockApiPost.mockResolvedValue({
        data: {
          files: [
            {
              preview_chunks: [
                {
                  content: "Hello from chunk one",
                  char_count: 20,
                  start: 0,
                  end: 20,
                },
              ],
            },
          ],
        },
      });
      render(<KnowledgeBaseUploadModal open={true} setOpen={jest.fn()} />, {
        wrapper: createWrapper(),
      });
      const fileInput = document.getElementById(
        "file-input",
      ) as HTMLInputElement;
      await user.upload(
        fileInput,
        new File(["Hello from chunk one"], "test.txt", { type: "text/plain" }),
      );
      await navigateToStep2(user);
      await waitFor(() =>
        expect(screen.getByText("Hello from chunk one")).toBeInTheDocument(),
      );
    });
  });

  // ── Add Sources Mode ───────────────────────────────────────────────────────

  describe("Add Sources Mode", () => {
    const existingKB = {
      name: "ExistingKnowledgeBase",
      embeddingModel: "text-embedding-3-small",
      embeddingProvider: "OpenAI",
    };

    it("disables the name input", async () => {
      render(
        <KnowledgeBaseUploadModal
          open={true}
          setOpen={jest.fn()}
          existingKnowledgeBase={existingKB}
        />,
        { wrapper: createWrapper() },
      );
      await waitFor(() =>
        expect(screen.getByTestId("kb-source-name-input")).toBeDisabled(),
      );
    });

    it('displays "Add Sources" as the modal title', async () => {
      render(
        <KnowledgeBaseUploadModal
          open={true}
          setOpen={jest.fn()}
          existingKnowledgeBase={existingKB}
        />,
        { wrapper: createWrapper() },
      );
      await waitFor(() =>
        expect(
          screen.getByRole("heading", { name: /Add Sources/i }),
        ).toBeInTheDocument(),
      );
    });

    it("shows the existing embedding model name instead of the model selector", async () => {
      render(
        <KnowledgeBaseUploadModal
          open={true}
          setOpen={jest.fn()}
          existingKnowledgeBase={existingKB}
        />,
        { wrapper: createWrapper() },
      );
      await waitFor(() =>
        expect(screen.getByText("text-embedding-3-small")).toBeInTheDocument(),
      );
      expect(
        screen.queryByTestId("embedding-model-select"),
      ).not.toBeInTheDocument();
    });

    it('labels the submit button "Add Sources"', async () => {
      render(
        <KnowledgeBaseUploadModal
          open={true}
          setOpen={jest.fn()}
          existingKnowledgeBase={existingKB}
          hideAdvanced={true}
        />,
        { wrapper: createWrapper() },
      );
      await waitFor(() =>
        expect(screen.getByTestId("kb-create-button")).toHaveTextContent(
          "Add Sources",
        ),
      );
    });
  });

  // ── Form Reset ─────────────────────────────────────────────────────────────

  describe("Form Reset", () => {
    it("resets form fields when the modal is closed via the close button", async () => {
      const user = userEvent.setup();
      const mockSetOpen = jest.fn();
      render(<KnowledgeBaseUploadModal open={true} setOpen={mockSetOpen} />, {
        wrapper: createWrapper(),
      });
      await user.type(
        screen.getByTestId("kb-source-name-input"),
        "SomeKnowledgeBase",
      );
      expect(screen.getByTestId("kb-source-name-input")).toHaveValue(
        "SomeKnowledgeBase",
      );

      // Closing the dialog triggers onOpenChange → resetForm()
      await user.click(screen.getByRole("button", { name: /close/i }));

      await waitFor(() =>
        expect(screen.getByTestId("kb-source-name-input")).toHaveValue(""),
      );
      expect(mockSetOpen).toHaveBeenCalledWith(false);
    });
  });
});
