import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { GlobalVariable } from "@/types/global_variables";
import DBProvidersPage from "../index";

// ---------------------------------------------------------------------------
// Characterization (golden-master) suite for the untouched 866-line page.
// It pins the observable behavior BEFORE the WP2 extraction so every
// extraction commit can be validated against it. No implementation details
// are asserted — only what a user (or consumer) can observe.
// ---------------------------------------------------------------------------

let mockGlobalVariables: GlobalVariable[] = [];

const postCalls: Array<Record<string, unknown>> = [];
const patchCalls: Array<Record<string, unknown>> = [];
const mockPostMutateAsync = jest.fn((params: Record<string, unknown>) => {
  postCalls.push(params);
  return Promise.resolve(undefined);
});
const mockPatchMutateAsync = jest.fn((params: Record<string, unknown>) => {
  patchCalls.push(params);
  return Promise.resolve(undefined);
});
const mockTestMutateAsync = jest.fn(() =>
  Promise.resolve({ ok: true, message: "cluster green" }),
);

const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();

jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: () => ({ data: mockGlobalVariables }),
  usePostGlobalVariables: () => ({
    mutateAsync: mockPostMutateAsync,
    isPending: false,
  }),
  usePatchGlobalVariables: () => ({
    mutateAsync: mockPatchMutateAsync,
    isPending: false,
  }),
}));

jest.mock(
  "@/controllers/API/queries/knowledge-bases/use-test-kb-connection",
  () => ({
    useTestDBProviderConnection: () => ({
      mutateAsync: mockTestMutateAsync,
      isPending: false,
    }),
  }),
);

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      setSuccessData: mockSetSuccessData,
      setErrorData: mockSetErrorData,
    }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

const STRINGS: Record<string, string> = {
  "settings.dbProviders.title": "DB Providers",
  "settings.dbProviders.description":
    "Configure vector-store providers for Knowledge Bases.",
  "settings.dbProviders.active": "Active",
  "settings.dbProviders.comingSoon": "Coming soon",
  "settings.dbProviders.comingSoonDescription":
    "This provider is stubbed in the Knowledge Base backend registry and will become configurable after the provider implementation is wired through end-to-end.",
  "settings.dbProviders.chromaDescription":
    "Chroma stores vectors on disk next to Langflow and is enabled by default. Selecting it here makes it the default provider for new Knowledge Bases.",
  "settings.dbProviders.chromaSelected": "Chroma selected",
  "settings.dbProviders.useChroma": "Use Chroma",
  "settings.dbProviders.save": "Save",
  "settings.dbProviders.useProvider": "Use {{provider}}",
  "settings.dbProviders.saveAndUseProvider": "Save and use {{provider}}",
  "settings.dbProviders.testConnection": "Test connection",
  "settings.dbProviders.savedAsGlobalVariable": "Saved as global variable",
  "settings.dbProviders.errorMissingConfig": "Missing required configuration",
  "settings.dbProviders.configSaved": "{{provider}} configuration saved",
};

jest.mock("react-i18next", () => ({
  // Consumed by src/i18n.ts, which is pulled in transitively through
  // the ui/badge → utils import chain.
  initReactI18next: { type: "3rdParty", init: () => {} },
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) => {
      const template = STRINGS[key] ?? (options?.defaultValue as string) ?? key;
      return template.replace(/\{\{(\w+)\}\}/g, (_match, name: string) =>
        String(options?.[name] ?? ""),
      );
    },
  }),
}));

const variable = (
  name: string,
  value: string | undefined,
  id = `id-${name}`,
): GlobalVariable =>
  ({ id, name, value, type: "Generic" }) as unknown as GlobalVariable;

const openSearchRequiredSaved = (): GlobalVariable[] => [
  variable("OPENSEARCH_URL", "https://localhost:9200"),
  variable("OPENSEARCH_USERNAME", "admin"),
  // Credential values come back masked/absent from the API — existence
  // of the variable is what the page keys off for secrets.
  variable("OPENSEARCH_PASSWORD", undefined),
  variable("OPENSEARCH_INDEX_NAME", "langflow"),
];

const getSaveButton = (name: RegExp) => screen.getByRole("button", { name });

beforeEach(() => {
  mockGlobalVariables = [];
  postCalls.length = 0;
  patchCalls.length = 0;
  jest.clearAllMocks();
});

describe("DBProvidersPage characterization", () => {
  describe("provider list", () => {
    it("renders the six providers in canonical order", () => {
      render(<DBProvidersPage />);
      const items = screen.getAllByTestId(/^db-provider-item-/);
      expect(items.map((item) => item.getAttribute("data-testid"))).toEqual([
        "db-provider-item-chroma",
        "db-provider-item-chroma_cloud",
        "db-provider-item-opensearch",
        "db-provider-item-astra",
        "db-provider-item-mongodb",
        "db-provider-item-postgres",
      ]);
    });

    it("marks chroma as the active provider when no backend variable exists", () => {
      render(<DBProvidersPage />);
      const chromaItem = screen.getByTestId("db-provider-item-chroma");
      expect(chromaItem).toHaveTextContent("Active");
      expect(
        chromaItem.querySelector('[data-testid="icon-Check"]'),
      ).toBeInTheDocument();
    });

    it("marks the provider stored in LANGFLOW_KNOWLEDGE_BACKEND as active", () => {
      mockGlobalVariables = [
        variable("LANGFLOW_KNOWLEDGE_BACKEND", "opensearch"),
        ...openSearchRequiredSaved(),
      ];
      render(<DBProvidersPage />);
      expect(
        screen.getByTestId("db-provider-item-opensearch"),
      ).toHaveTextContent("Active");
      expect(
        screen.getByTestId("db-provider-item-chroma"),
      ).not.toHaveTextContent("Active");
    });

    it("shows a coming-soon badge for astra, mongodb and postgres", () => {
      render(<DBProvidersPage />);
      for (const id of ["astra", "mongodb", "postgres"]) {
        expect(screen.getByTestId(`db-provider-item-${id}`)).toHaveTextContent(
          "Coming soon",
        );
      }
    });
  });

  describe("chroma panel (default selection)", () => {
    it("shows a disabled 'Chroma selected' action while chroma is active", () => {
      render(<DBProvidersPage />);
      const button = getSaveButton(/chroma selected/i);
      expect(button).toBeDisabled();
      expect(screen.queryByTestId("db-provider-test-connection")).toBeNull();
    });
  });

  describe("opensearch panel", () => {
    const openOpenSearch = async () => {
      const user = userEvent.setup();
      render(<DBProvidersPage />);
      await user.click(screen.getByTestId("db-provider-item-opensearch"));
      return user;
    };

    it("renders text fields with variable keys, defaults and both TLS toggles", async () => {
      await openOpenSearch();
      for (const key of [
        "OPENSEARCH_URL",
        "OPENSEARCH_USERNAME",
        "OPENSEARCH_PASSWORD",
        "OPENSEARCH_INDEX_NAME",
        "OPENSEARCH_VECTOR_FIELD",
        "OPENSEARCH_TEXT_FIELD",
      ]) {
        expect(screen.getByText(key)).toBeInTheDocument();
      }
      // Optional fields come pre-filled with their defaults.
      expect(screen.getByDisplayValue("vector_field")).toBeInTheDocument();
      expect(screen.getByDisplayValue("text")).toBeInTheDocument();
      // Both TLS toggles render checked (defaultValue true).
      expect(
        screen.getByTestId("db-provider-toggle-OPENSEARCH_USE_SSL"),
      ).toHaveAttribute("aria-checked", "true");
      expect(
        screen.getByTestId("db-provider-toggle-OPENSEARCH_VERIFY_CERTS"),
      ).toHaveAttribute("aria-checked", "true");
    });

    it("keeps Save and Test connection disabled until every required field has a value", async () => {
      const user = await openOpenSearch();
      const save = getSaveButton(/save and use opensearch/i);
      const test = screen.getByTestId("db-provider-test-connection");
      expect(save).toBeDisabled();
      expect(test).toBeDisabled();

      const [url, username, indexName] = [
        "https://localhost:9200",
        "admin",
        "langflow",
      ];
      const textboxes = screen.getAllByRole("textbox");
      // textboxes: URL, Username, Index name, Vector field, Text field
      await user.type(textboxes[0], url);
      await user.type(textboxes[1], username);
      expect(save).toBeDisabled();
      const password = document.querySelector('input[type="password"]');
      await user.type(password as Element, "secret");
      await user.type(textboxes[2], indexName);

      expect(save).toBeEnabled();
      expect(test).toBeEnabled();
    });

    it("masks a configured secret and offers plain activation when hydrated", async () => {
      mockGlobalVariables = openSearchRequiredSaved();
      const user = userEvent.setup();
      render(<DBProvidersPage />);
      await user.click(screen.getByTestId("db-provider-item-opensearch"));

      const password = document.querySelector('input[type="password"]');
      expect(password).toHaveValue("••••••••");
      // Hydrated + no session edits → button switches to plain activation.
      const useButton = getSaveButton(/^use opensearch$/i);
      expect(useButton).toBeEnabled();
    });

    it("saves new required fields as global variables and activates the provider", async () => {
      const user = await openOpenSearch();
      const textboxes = screen.getAllByRole("textbox");
      await user.type(textboxes[0], "https://localhost:9200");
      await user.type(textboxes[1], "admin");
      await user.type(
        document.querySelector('input[type="password"]') as Element,
        "secret",
      );
      await user.type(textboxes[2], "langflow");

      await user.click(getSaveButton(/save and use opensearch/i));

      await waitFor(() => {
        expect(mockSetSuccessData).toHaveBeenCalledWith({
          title: "OpenSearch configuration saved",
        });
      });

      const byName = Object.fromEntries(
        postCalls.map((call) => [call.name, call]),
      );
      expect(byName.OPENSEARCH_URL).toMatchObject({
        value: "https://localhost:9200",
        type: "Generic",
      });
      expect(byName.OPENSEARCH_USERNAME).toMatchObject({ value: "admin" });
      // Secrets persist as Credential-type variables.
      expect(byName.OPENSEARCH_PASSWORD).toMatchObject({
        value: "secret",
        type: "Credential",
      });
      expect(byName.OPENSEARCH_INDEX_NAME).toMatchObject({
        value: "langflow",
      });
      // Activation writes the backend selector variable.
      expect(byName.LANGFLOW_KNOWLEDGE_BACKEND).toMatchObject({
        value: "opensearch",
      });
      expect(patchCalls).toHaveLength(0);
    });

    it("updates existing variables through PATCH instead of re-creating them", async () => {
      mockGlobalVariables = openSearchRequiredSaved();
      const user = userEvent.setup();
      render(<DBProvidersPage />);
      await user.click(screen.getByTestId("db-provider-item-opensearch"));

      const textboxes = screen.getAllByRole("textbox");
      await user.clear(textboxes[0]);
      await user.type(textboxes[0], "https://other:9200");
      await user.click(getSaveButton(/save and use opensearch/i));

      await waitFor(() => {
        expect(
          patchCalls.some(
            (call) =>
              call.id === "id-OPENSEARCH_URL" &&
              call.value === "https://other:9200",
          ),
        ).toBe(true);
      });
      // The untouched, already-saved fields are not re-created.
      expect(
        postCalls.filter((call) => call.name === "OPENSEARCH_PASSWORD"),
      ).toHaveLength(0);
    });
  });

  describe("coming-soon panel", () => {
    it("shows the stub description and no actions for astra", async () => {
      const user = userEvent.setup();
      render(<DBProvidersPage />);
      await user.click(screen.getByTestId("db-provider-item-astra"));
      expect(
        screen.getByText(/stubbed in the Knowledge Base backend registry/),
      ).toBeInTheDocument();
      expect(screen.queryByTestId("db-provider-test-connection")).toBeNull();
      expect(screen.queryByRole("button", { name: /Save/ })).toBeNull();
    });
  });
});
