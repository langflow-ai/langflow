import type { Route } from "@playwright/test";
import { expect, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";
import type { LangflowPage } from "../utils/types";

interface MockModel {
  model_name: string;
  metadata: Record<string, unknown>;
}

interface MockProvider {
  provider: string;
  is_enabled: boolean;
  is_configured: boolean;
  api_docs_url?: string;
  models: MockModel[];
}

interface MockProviderVariable {
  variable_name: string;
  variable_key: string;
  required: boolean;
  is_secret: boolean;
  is_list: boolean;
  options: string[];
}

interface MockGlobalVariable {
  id: string;
  name: string;
  type: "Credential" | "Generic";
  value?: string;
  default_fields: string[];
  category?: string;
}

const openAiProvider: MockProvider = {
  provider: "OpenAI",
  is_enabled: true,
  is_configured: true,
  api_docs_url: "https://platform.openai.com/api-keys",
  models: [
    {
      model_name: "gpt-4.1",
      metadata: { model_type: "llm", tool_calling: true, reasoning: true },
    },
    {
      model_name: "gpt-3.5-turbo",
      metadata: { model_type: "llm", deprecated: true },
    },
    {
      model_name: "text-embedding-3-large",
      metadata: { model_type: "embeddings" },
    },
  ],
};

const anthropicProvider: MockProvider = {
  provider: "Anthropic",
  is_enabled: false,
  is_configured: false,
  api_docs_url: "https://console.anthropic.com/settings/keys",
  models: [
    {
      model_name: "claude-opus-4",
      metadata: { model_type: "llm", reasoning: true, vision: true },
    },
  ],
};

const ollamaProvider: MockProvider = {
  provider: "Ollama",
  is_enabled: false,
  is_configured: false,
  models: [],
};

const defaultProviders: MockProvider[] = [
  openAiProvider,
  anthropicProvider,
  ollamaProvider,
];

const defaultProviderVariables: Record<string, MockProviderVariable[]> = {
  OpenAI: [
    {
      variable_name: "API Key",
      variable_key: "OPENAI_API_KEY",
      required: true,
      is_secret: true,
      is_list: false,
      options: [],
    },
  ],
  Anthropic: [
    {
      variable_name: "API Key",
      variable_key: "ANTHROPIC_API_KEY",
      required: true,
      is_secret: true,
      is_list: false,
      options: [],
    },
  ],
  Ollama: [
    {
      variable_name: "Base URL",
      variable_key: "OLLAMA_BASE_URL",
      required: false,
      is_secret: false,
      is_list: false,
      options: [],
    },
  ],
};

const defaultEnabledModels: Record<string, Record<string, boolean>> = {
  OpenAI: { "gpt-4.1": true, "gpt-3.5-turbo": false },
};

const defaultGlobalVariables: MockGlobalVariable[] = [
  {
    id: "a11y-var-openai",
    name: "OPENAI_API_KEY",
    type: "Credential",
    default_fields: [],
    category: "Global",
  },
];

async function disableAnimations(page: LangflowPage) {
  await page.addStyleTag({
    content: `
      *,
      *::before,
      *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
        scroll-behavior: auto !important;
      }
    `,
  });
}

async function mockProviderCatalog(
  page: LangflowPage,
  {
    providers = defaultProviders,
    providerVariables = defaultProviderVariables,
    enabledModels = defaultEnabledModels,
    providersDelayMs = 0,
  }: {
    providers?: MockProvider[];
    providerVariables?: Record<string, MockProviderVariable[]>;
    enabledModels?: Record<string, Record<string, boolean>>;
    providersDelayMs?: number;
  } = {},
) {
  await page.route(
    /\/api\/v1\/models\?include_deprecated=true$/,
    async (route: Route) => {
      if (providersDelayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, providersDelayMs));
      }
      await route.fulfill({ json: providers });
    },
  );

  await page.route(
    /\/api\/v1\/models\/enabled_models$/,
    async (route: Route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({ json: { disabled_models: [] } });
        return;
      }
      await route.fulfill({ json: { enabled_models: enabledModels } });
    },
  );

  await page.route(
    /\/api\/v1\/models\/provider-variable-mapping$/,
    async (route: Route) => {
      await route.fulfill({ json: providerVariables });
    },
  );
}

async function mockValidateProvider(
  page: LangflowPage,
  result: { valid: boolean; error?: string | null },
) {
  await page.route(
    /\/api\/v1\/models\/validate-provider$/,
    async (route: Route) => {
      await route.fulfill({
        json: { valid: result.valid, error: result.error ?? null },
      });
    },
  );
}

async function mockGlobalVariables(
  page: LangflowPage,
  initial: MockGlobalVariable[] = defaultGlobalVariables,
) {
  let currentVariables = [...initial];

  await page.route(/\/api\/v1\/variables\/$/, async (route: Route) => {
    const request = route.request();
    const method = request.method();

    if (method === "GET") {
      await route.fulfill({ json: currentVariables });
      return;
    }

    if (method === "POST") {
      const body = request.postDataJSON() as {
        name: string;
        value: string;
        type: string;
        category?: string;
        default_fields?: string[];
      };
      const created: MockGlobalVariable = {
        id: `a11y-generated-${body.name.toLowerCase()}`,
        name: body.name,
        type: body.type === "Credential" ? "Credential" : "Generic",
        default_fields: body.default_fields ?? [],
        category: body.category,
      };
      currentVariables = [...currentVariables, created];
      await route.fulfill({
        json: { name: created.name, id: created.id, type: created.type },
      });
      return;
    }

    await route.continue();
  });

  await page.route(/\/api\/v1\/variables\/[\w-]+$/, async (route: Route) => {
    const method = route.request().method();

    if (method === "PATCH") {
      await route.fulfill({ json: { message: "Variable updated" } });
      return;
    }

    if (method === "DELETE") {
      const url = route.request().url();
      currentVariables = currentVariables.filter(
        (variable) => !url.endsWith(`/${variable.id}`),
      );
      await route.fulfill({ json: { message: "Variable deleted" } });
      return;
    }

    await route.continue();
  });
}

async function openModelProvidersRoute(page: LangflowPage) {
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto("/settings/model-providers");
  await disableAnimations(page);
  await expect(page.getByTestId("settings_menu_header")).toContainText(
    "Model Providers",
    { timeout: TIMEOUTS.standard },
  );
  await page
    .waitForLoadState("networkidle", { timeout: TIMEOUTS.medium })
    .catch(() => {});
}

test.describe("Model providers route accessibility", () => {
  test(
    "scans populated provider list default state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await mockProviderCatalog(page);
      await mockGlobalVariables(page);
      await openModelProvidersRoute(page);
      await expect(page.getByTestId("provider-item-OpenAI")).toBeVisible();
      await expect(page.getByTestId("provider-item-Anthropic")).toBeVisible();
      await expect(page.getByTestId("provider-item-Ollama")).toBeVisible();

      await page.runA11yScan("settings-model-providers-data-rich");
    },
  );

  test(
    "scans provider list loading state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await mockProviderCatalog(page, { providersDelayMs: 6000 });
      await mockGlobalVariables(page);
      await awaitBootstrapTest(page, { skipModal: true });
      await page.goto("/settings/model-providers");
      await disableAnimations(page);
      await expect(page.getByTestId("settings_menu_header")).toContainText(
        "Model Providers",
        { timeout: TIMEOUTS.standard },
      );
      await expect(page.getByTestId("provider-list-loading")).toBeVisible({
        timeout: TIMEOUTS.short,
      });

      await page.runA11yScan("settings-model-providers-loading");
    },
  );

  test(
    "scans provider search empty state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await mockProviderCatalog(page);
      await mockGlobalVariables(page);
      await openModelProvidersRoute(page);
      await page.getByTestId("provider-search-input").fill("zzz-no-match");
      await expect(page.getByTestId("provider-list-empty")).toBeVisible();

      await page.runA11yScan("settings-model-providers-search-empty");
    },
  );

  test(
    "scans configured provider selected with credential form",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await mockProviderCatalog(page);
      await mockGlobalVariables(page);
      await openModelProvidersRoute(page);
      await page.getByTestId("provider-item-OpenAI").click();
      await expect(
        page.getByTestId("provider-variable-input-OPENAI_API_KEY"),
      ).toBeVisible();
      await expect(page.getByTestId("model-provider-selection")).toBeVisible();
      await expect(page.getByTestId("llm-toggle-gpt-4.1")).toBeVisible();

      await page.runA11yScan("settings-model-providers-provider-selected");
    },
  );

  test(
    "scans masked secret field entering editing state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await mockProviderCatalog(page);
      await mockGlobalVariables(page);
      await openModelProvidersRoute(page);
      await page.getByTestId("provider-item-OpenAI").click();
      const secretInput = page.getByTestId(
        "provider-variable-input-OPENAI_API_KEY",
      );
      await expect(secretInput).toBeVisible();
      await secretInput.click();
      await expect(secretInput).toHaveAttribute("type", "password");

      await page.runA11yScan("settings-model-providers-secret-editing");
    },
  );

  test(
    "scans deprecated models disclosure expanded state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await mockProviderCatalog(page);
      await mockGlobalVariables(page);
      await openModelProvidersRoute(page);
      await page.getByTestId("provider-item-OpenAI").click();
      await expect(page.getByTestId("llm-deprecated-summary")).toBeVisible();
      await page.getByTestId("llm-deprecated-summary").click();
      await expect(page.getByTestId("llm-toggle-gpt-3.5-turbo")).toBeVisible();

      await page.runA11yScan("settings-model-providers-deprecated-expanded");
    },
  );

  test(
    "scans model search empty state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await mockProviderCatalog(page);
      await mockGlobalVariables(page);
      await openModelProvidersRoute(page);
      await page.getByTestId("provider-item-OpenAI").click();
      await page.getByTestId("model-search-input").fill("zzz-no-match");
      await expect(page.getByTestId("model-search-empty")).toBeVisible();

      await page.runA11yScan("settings-model-providers-model-search-empty");
    },
  );

  test(
    "scans model toggle switch flipped state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await mockProviderCatalog(page);
      await mockGlobalVariables(page);
      await openModelProvidersRoute(page);
      await page.getByTestId("provider-item-OpenAI").click();
      const toggle = page.getByTestId("llm-toggle-gpt-4.1");
      await expect(toggle).toHaveAttribute("aria-checked", "true");
      await toggle.click();
      await expect(toggle).toHaveAttribute("aria-checked", "false");
      await expect(toggle).toHaveAttribute("aria-label", "Enable gpt-4.1");

      await page.runA11yScan("settings-model-providers-model-toggled");
    },
  );

  test(
    "scans invalid credential validation error state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await mockProviderCatalog(page);
      await mockGlobalVariables(page, []);
      await mockValidateProvider(page, {
        valid: false,
        error: "The provided API key is invalid.",
      });
      await openModelProvidersRoute(page);
      await page.getByTestId("provider-item-Anthropic").click();
      await page
        .getByTestId("provider-variable-input-ANTHROPIC_API_KEY") // pragma: allowlist secret
        .fill("sk-ant-a11y-invalid-redacted"); // pragma: allowlist secret
      await page.getByRole("button", { name: "Save", exact: true }).click();
      await expect(page.getByText("Validation Failed")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await page.runA11yScan("settings-model-providers-validation-error");
    },
  );

  test(
    "scans successful credential save confirmation state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await mockProviderCatalog(page);
      await mockGlobalVariables(page, []);
      await mockValidateProvider(page, { valid: true, error: null });
      await openModelProvidersRoute(page);
      await page.getByTestId("provider-item-Anthropic").click();
      await page
        .getByTestId("provider-variable-input-ANTHROPIC_API_KEY") // pragma: allowlist secret
        .fill("sk-ant-a11y-valid-redacted"); // pragma: allowlist secret
      await page.getByRole("button", { name: "Save", exact: true }).click();
      await expect(page.getByText("Anthropic Configuration Saved")).toBeVisible(
        { timeout: TIMEOUTS.standard },
      );

      await page.runA11yScan("settings-model-providers-validation-success");
    },
  );

  test(
    "scans disconnect confirmation warning state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await mockProviderCatalog(page);
      await mockGlobalVariables(page);
      await openModelProvidersRoute(page);
      await page.getByTestId("provider-item-OpenAI").click();
      await page.getByRole("button", { name: "Disconnect" }).click();
      await expect(
        page.getByText(
          "Disconnecting an API key will disable all of the provider's models being used in a flow.",
        ),
      ).toBeVisible();

      await page.runA11yScan("settings-model-providers-disconnect-warning");
    },
  );

  test(
    "scans provider without required configuration",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await mockProviderCatalog(page);
      await mockGlobalVariables(page);
      await openModelProvidersRoute(page);
      await page.getByTestId("provider-item-Ollama").click();
      await expect(
        page.getByRole("button", { name: "Activate Ollama" }),
      ).toBeVisible();
      await expect(page.getByText("No models available")).toBeVisible();

      await page.runA11yScan("settings-model-providers-no-config-required");
    },
  );
});
