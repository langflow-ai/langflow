import { expect, type LangflowPage } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TIMEOUTS } from "../../utils/constants/timeouts";

export const SAMPLE_FILE_PATH = "tests/assets/resume.txt";
export const SAMPLE_FILE_PATH_2 = "tests/assets/test-file.txt";

export const KB_LIST_GLOB = "**/api/v1/knowledge_bases/";
export const KB_RUNS_LIST_GLOB = "**/api/v1/knowledge_bases/*/runs*";
export const KB_RUN_DETAIL_GLOB = "**/api/v1/knowledge_bases/*/runs/*";
export const KB_CHUNKS_GLOB = "**/api/v1/knowledge_bases/*/chunks*";
export const KB_METADATA_KEYS_GLOB =
  "**/api/v1/knowledge_bases/*/metadata/keys*";
export const KB_PREVIEW_GLOB = "**/api/v1/knowledge_bases/preview-chunks";
export const MODELS_GLOB = "**/api/v1/models**";
export const ENABLED_MODELS_GLOB = "**/api/v1/models/enabled_models**";
export const VARIABLES_GLOB = "**/api/v1/variables**";

export const RELEASE = { tag: ["@release", "@workspace"] };

export type SeededKnowledgeBase = {
  id: string;
  dir_name: string;
  name: string;
  embedding_provider: string;
  embedding_model: string;
  size: number;
  words: number;
  characters: number;
  chunks: number;
  avg_chunk_size: number;
  status: string;
  source_types: string[];
  backend_type: string;
};

export const SEEDED_KNOWLEDGE_BASES: SeededKnowledgeBase[] = [
  {
    id: "kb-alpha",
    dir_name: "alpha_kb",
    name: "Alpha Knowledge Base",
    embedding_provider: "OpenAI",
    embedding_model: "text-embedding-3-small",
    size: 1024,
    words: 1200,
    characters: 8000,
    chunks: 42,
    avg_chunk_size: 190,
    status: "ready",
    source_types: ["pdf"],
    backend_type: "local",
  },
  {
    id: "kb-beta",
    dir_name: "beta_kb",
    name: "Beta Knowledge Base",
    embedding_provider: "OpenAI",
    embedding_model: "text-embedding-3-large",
    size: 2048,
    words: 2400,
    characters: 16000,
    chunks: 88,
    avg_chunk_size: 182,
    status: "ready",
    source_types: ["txt"],
    backend_type: "local",
  },
];

export const SEEDED_STATUS_KNOWLEDGE_BASES: SeededKnowledgeBase[] = [
  SEEDED_KNOWLEDGE_BASES[0],
  {
    ...SEEDED_KNOWLEDGE_BASES[0],
    id: "kb-ingesting",
    dir_name: "ingesting_kb",
    name: "Ingesting Knowledge Base",
    status: "ingesting",
  },
  {
    ...SEEDED_KNOWLEDGE_BASES[0],
    id: "kb-failed",
    dir_name: "failed_kb",
    name: "Failed Knowledge Base",
    status: "failed",
  },
];

export const SEEDED_RUN = {
  id: "run-1",
  source_type: "file_upload",
  status: "succeeded",
  started_at: "2024-01-01T00:00:00Z",
  succeeded: 2,
  failed: 0,
  skipped: 0,
  chunks_created: 42,
  total_items: 2,
  total_bytes: 2048,
  job_id: "job-1",
};

export const SEEDED_RUN_DETAIL = {
  ...SEEDED_RUN,
  error_message: null,
  items: [
    {
      item_id: "item-1",
      display_name: "handbook.txt",
      status: "succeeded",
      chunks_created: 42,
      error_message: null,
    },
  ],
};

export const SEEDED_CHUNKS_RESPONSE = {
  chunks: [
    {
      id: "chunk-1",
      content:
        "Langflow lets you compose AI workflows visually. This chunk is long " +
        "enough to exercise the readable body-text path in the chunk card.",
      char_count: 132,
      metadata: {
        file_name: "handbook.txt",
        source_metadata: JSON.stringify({ team: "docs" }),
      },
    },
    {
      id: "chunk-2",
      content: "A second chunk so the list renders more than one card.",
      char_count: 54,
      metadata: { file_name: "handbook.txt" },
    },
  ],
  total: 2,
  page: 1,
  limit: 10,
  total_pages: 1,
};

const MODEL_PROVIDERS = [
  {
    provider: "OpenAI",
    icon: "OpenAI",
    is_enabled: true,
    is_configured: true,
    models: [
      {
        model_name: "text-embedding-3-small",
        metadata: { model_type: "embeddings" },
      },
    ],
  },
];

export async function disableAnimations(page: LangflowPage) {
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

export async function mockKnowledgeBases(
  page: LangflowPage,
  rows: SeededKnowledgeBase[],
) {
  await page.route(KB_LIST_GLOB, (route) => route.fulfill({ json: rows }));
}

export async function mockIngestionRuns(page: LangflowPage, runs: unknown[]) {
  await page.route(KB_RUNS_LIST_GLOB, (route) =>
    route.fulfill({
      json: {
        runs,
        total: runs.length,
        page: 1,
        limit: 10,
        total_pages: runs.length > 0 ? 1 : 0,
      },
    }),
  );
}

export async function mockIngestionRunDetail(
  page: LangflowPage,
  detail: unknown,
) {
  await page.route(KB_RUN_DETAIL_GLOB, (route) =>
    route.fulfill({ json: detail }),
  );
}

export async function mockModels(page: LangflowPage) {
  await page.route(VARIABLES_GLOB, (route) => route.fulfill({ json: [] }));
  await page.route(MODELS_GLOB, (route) =>
    route.fulfill({ json: MODEL_PROVIDERS }),
  );
  await page.route(ENABLED_MODELS_GLOB, (route) =>
    route.fulfill({ json: { enabled_models: {} } }),
  );
}

export async function mockChunks(page: LangflowPage, response: unknown) {
  await page.route(KB_CHUNKS_GLOB, (route) =>
    route.fulfill({ json: response }),
  );
}

export async function mockMetadataKeys(
  page: LangflowPage,
  keys: Record<string, string[]>,
) {
  await page.route(KB_METADATA_KEYS_GLOB, (route) =>
    route.fulfill({ json: { keys } }),
  );
}

export async function openKnowledgeBasesRoute(page: LangflowPage) {
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto("/assets/knowledge-bases");
  await disableAnimations(page);
  await expect(page).toHaveURL(/\/assets\/knowledge-bases\/?$/, {
    timeout: TIMEOUTS.standard,
  });
  await expect(page.getByTestId("mainpage_title")).toContainText("Knowledge", {
    timeout: TIMEOUTS.standard,
  });
}

export async function openChunksRoute(page: LangflowPage, sourceId: string) {
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto(`/assets/knowledge-bases/${sourceId}/chunks`);
  await disableAnimations(page);
  await expect(page.getByTestId("source-chunks-wrapper")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
}

export async function settleNetwork(page: LangflowPage) {
  await page
    .waitForLoadState("networkidle", { timeout: TIMEOUTS.medium })
    .catch(() => {});
}

export async function openCreateModal(page: LangflowPage) {
  await mockModels(page);
  await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
  await mockIngestionRuns(page, []);
  await openKnowledgeBasesRoute(page);
  await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
  await page.getByRole("button", { name: /add knowledge/i }).click();
  await expect(page.getByRole("dialog")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
  await expect(page.getByTestId("kb-source-name-input")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
}

export async function openAddSourcesModal(page: LangflowPage) {
  await mockModels(page);
  await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
  await mockIngestionRuns(page, [SEEDED_RUN]);
  await openKnowledgeBasesRoute(page);
  await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
  await page.getByTestId("kb-row-update-button").first().click();
  await expect(page.getByRole("dialog")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
  await expect(page.getByTestId("kb-ingestion-history-panel")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
}

export async function attachFiles(page: LangflowPage, paths: string[]) {
  await page.getByTestId("kb-source-name-input").fill("review_kb");
  await page.locator("#file-input").setInputFiles(paths);
  await expect(page.getByTestId("kb-file-metadata-toggle-0")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
}

export async function openKnowledgeBaseDrawer(
  page: LangflowPage,
  kbName = "Alpha Knowledge Base",
) {
  await page.getByText(kbName).click();
  await expect(page.getByRole("heading", { name: kbName })).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
}

export async function gateRoute(
  page: LangflowPage,
  glob: string,
  json: unknown,
): Promise<() => void> {
  let release: () => void = () => {};
  const ready = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(glob, async (route) => {
    await ready;
    await route.fulfill({ json });
  });
  return release;
}
