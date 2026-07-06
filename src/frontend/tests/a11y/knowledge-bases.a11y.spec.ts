import { expect, type LangflowPage, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";
import {
  attachFiles,
  disableAnimations,
  gateRoute,
  KB_CHUNKS_GLOB,
  KB_LIST_GLOB,
  KB_PREVIEW_GLOB,
  KB_RUNS_LIST_GLOB,
  mockChunks,
  mockIngestionRunDetail,
  mockIngestionRuns,
  mockKnowledgeBases,
  mockMetadataKeys,
  openAddSourcesModal,
  openChunksRoute,
  openCreateModal,
  openKnowledgeBaseDrawer,
  openKnowledgeBasesRoute,
  RELEASE,
  SAMPLE_FILE_PATH,
  SAMPLE_FILE_PATH_2,
  SEEDED_CHUNKS_RESPONSE,
  SEEDED_KNOWLEDGE_BASES,
  SEEDED_RUN,
  SEEDED_RUN_DETAIL,
  SEEDED_STATUS_KNOWLEDGE_BASES,
  settleNetwork,
} from "./helpers/knowledge-bases.fixtures";

// Accessibility scans for /assets/knowledge-bases and its chunks child route.
// Each distinct UI surface gets its own runA11yScan label; tests are grouped
// into data-driven scenarios and serial journeys to cut bootstrap overhead.

// Rules triggered by shared app chrome, the global theme, or third-party
// widgets that the knowledge-base feature does not own. Each entry was
// validated against the report DOM (coverage/accessibility-reports) and, where
// relevant, the dependency source. Suppressed so scans reflect KB-specific
// issues rather than app-wide concerns tracked elsewhere.
const KB_IGNORE_RULES = [
  // aria_content_in_landmark: the flagged nodes are the LEFT folder sidebar
  // (SideBarFoldersButtonsComponent — upload-project-button, sidebar-nav-*,
  // "Options for …") and Radix portal menus rendered on document.body. Both are
  // shared MainPage chrome / framework portals, not KB markup.
  "aria_content_in_landmark",
  // label_name_visible: only the header GitHub button (aria-label="GitHub 151k"
  // vs visible "151k"). Shared header chrome.
  "label_name_visible",
  // text_contrast_sufficient (WCAG 1.4.3, IBM Level 1): every occurrence comes
  // from GLOBAL theme tokens — `text-muted-foreground` (~4.40:1 vs the 4.5:1
  // minimum) and `text-accent-emerald-foreground` (~3.86:1) — used app-wide, not
  // KB-specific colors. Fixing means adjusting the design tokens (all surfaces),
  // which is out of scope for KB markup. NOTE: this is a real, tracked Level-1
  // gap; it should be resolved at the theme level, not permanently ignored.
  "text_contrast_sufficient",
  // AG Grid 32 + framework focus guards — not fixable from application code:
  // • element_tabbable_role_valid: AG-Grid tab-guard divs (tabindex="0"
  //   role="presentation") and Radix focus guards (data-radix-focus-guard).
  // • aria_widget_labelled: AG-Grid exposes no gridOptions/GridApi to set an
  //   aria-label on its role="treegrid" root.
  // • aria_child_tabbable: AG-Grid rowgroups and cmdk's role="listbox" have no
  //   individually tabbable descendants (both drive selection via
  //   aria-activedescendant — the correct composite-widget pattern).
  "element_tabbable_role_valid",
  "aria_widget_labelled",
  "aria_child_tabbable",
  // Radix / cmdk framework limitations — validated against the report DOM and the
  // dependency source; none are fixable from KB markup:
  // • aria_hidden_nontabbable: whenever a Radix overlay (Dialog/Select/Popover/
  //   DropdownMenu) opens, Radix sets aria-hidden="true" on the ENTIRE background
  //   subtree but does not set `inert`, so every focusable descendant behind the
  //   overlay stays tabbable. The report flags the whole background — app header,
  //   folder sidebar, AND KB content (search-kb-input, AG-Grid, chunk buttons)
  //   alike. It is not a per-element defect; only an app-wide `inert` treatment
  //   of the background would resolve it, which is outside the KB feature.
  "aria_hidden_nontabbable",
  // • label_content_exists / label_ref_valid: cmdk's <Command> root always renders
  //   `<label cmdk-label htmlFor={inputId} style={visuallyHidden}>{label}</label>`
  //   (see node_modules/cmdk/dist/index.js, style var `rt` — the exact
  //   clip:rect(0,0,0,0) label the checker flags). With no `label` prop it is empty
  //   (label_content_exists) and its `htmlFor` targets the CommandInput that only
  //   mounts while the popup is open (label_ref_valid). Every combobox built on
  //   Popover+Command (metadata filter, model + db-provider dropdowns) inherits it.
  "label_content_exists",
  "label_ref_valid",
  // • combobox_autocomplete_valid: cmdk's CommandInput hardcodes
  //   aria-autocomplete="list" role="combobox" on the input inside the popup, which
  //   the checker treats as misplaced relative to the trigger. Framework-owned.
  "combobox_autocomplete_valid",
];

type A11yScenario = {
  name: string;
  run: (page: LangflowPage) => Promise<void>;
};

const KB_LIST_SCENARIOS: A11yScenario[] = [
  {
    name: "empty state",
    run: async (page) => {
      await mockKnowledgeBases(page, []);
      await openKnowledgeBasesRoute(page);
      await expect(
        page.getByRole("heading", { name: /no knowledge bases/i }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await settleNetwork(page);
      await page.runA11yScan("kb-empty", { ignoreRules: KB_IGNORE_RULES });
    },
  },
  {
    name: "populated table",
    run: async (page) => {
      await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
      await openKnowledgeBasesRoute(page);
      await expect(page.getByTestId("search-kb-input")).toBeVisible();
      await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await settleNetwork(page);
      await page.runA11yScan("kb-populated", { ignoreRules: KB_IGNORE_RULES });
    },
  },
  {
    name: "row status variants",
    run: async (page) => {
      await mockKnowledgeBases(page, SEEDED_STATUS_KNOWLEDGE_BASES);
      await openKnowledgeBasesRoute(page);
      await expect(page.getByText("Ingesting Knowledge Base")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(page.getByText("Failed Knowledge Base")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await settleNetwork(page);
      await page.runA11yScan("kb-row-status-variants", {
        ignoreRules: KB_IGNORE_RULES,
      });
    },
  },
];

const KB_CHUNKS_SCENARIOS: A11yScenario[] = [
  {
    name: "populated chunks list",
    run: async (page) => {
      await mockChunks(page, SEEDED_CHUNKS_RESPONSE);
      await openChunksRoute(page, "alpha_kb");
      await expect(page.getByTestId("chunks-search-input")).toBeVisible();
      await expect(
        page.getByText(/langflow lets you compose ai workflows/i),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await settleNetwork(page);
      await page.runA11yScan("kbchunks-populated", {
        ignoreRules: KB_IGNORE_RULES,
      });
    },
  },
  {
    name: "no-results state",
    run: async (page) => {
      await mockChunks(page, {
        chunks: [],
        total: 0,
        page: 1,
        limit: 10,
        total_pages: 0,
      });
      await openChunksRoute(page, "alpha_kb");
      await expect(page.getByText(/no chunks found/i)).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await settleNetwork(page);
      await page.runA11yScan("kbchunks-empty", {
        ignoreRules: KB_IGNORE_RULES,
      });
    },
  },
  {
    name: "pagination controls",
    run: async (page) => {
      await mockChunks(page, {
        ...SEEDED_CHUNKS_RESPONSE,
        total: 25,
        total_pages: 3,
      });
      await openChunksRoute(page, "alpha_kb");
      await expect(page.getByTestId("chunks-page-size-select")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await settleNetwork(page);
      await page.runA11yScan("kbchunks-pagination", {
        ignoreRules: KB_IGNORE_RULES,
      });
    },
  },
];

test.describe("knowledge bases route accessibility", () => {
  for (const scenario of KB_LIST_SCENARIOS) {
    test(`scans the ${scenario.name}`, RELEASE, async ({ page }) => {
      await scenario.run(page);
    });
  }

  test("scans the loading state", RELEASE, async ({ page }) => {
    let releaseList: () => void = () => {};
    const listReady = new Promise<void>((resolve) => {
      releaseList = resolve;
    });
    await page.route(KB_LIST_GLOB, async (route) => {
      await listReady;
      await route.fulfill({ json: SEEDED_KNOWLEDGE_BASES });
    });

    await awaitBootstrapTest(page, { skipModal: true });
    await page.goto("/assets/knowledge-bases");
    await disableAnimations(page);

    await expect(page.getByText(/loading knowledge bases/i)).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await page.runA11yScan("kb-loading", { ignoreRules: KB_IGNORE_RULES });

    releaseList();
    await settleNetwork(page);
  });

  test("scans the fetch error toast", RELEASE, async ({ page }) => {
    page.allowFlowErrors();
    await page.route(KB_LIST_GLOB, (route) =>
      route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Bad request" }),
      }),
    );

    await awaitBootstrapTest(page, { skipModal: true });
    await page.goto("/assets/knowledge-bases");
    await disableAnimations(page);

    await expect(page.getByText(/failed to load knowledge bases/i)).toBeVisible(
      { timeout: TIMEOUTS.standard },
    );
    await page.runA11yScan("kb-error", { ignoreRules: KB_IGNORE_RULES });
  });

  test("scans selection and bulk-delete states", RELEASE, async ({ page }) => {
    await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
    await openKnowledgeBasesRoute(page);
    await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });

    await page.locator(".ag-header-select-all").first().click();
    const deleteSelected = page.getByRole("button", { name: /^Delete \(/ });
    await expect(deleteSelected).toBeVisible({ timeout: TIMEOUTS.standard });
    await page.runA11yScan("kb-selection-mode", {
      ignoreRules: KB_IGNORE_RULES,
    });

    await deleteSelected.click();
    await expect(
      page.getByTestId("btn_delete_delete_confirmation_modal"),
    ).toBeVisible({ timeout: TIMEOUTS.standard });
    await page.runA11yScan("kb-bulk-delete-modal-open", {
      ignoreRules: KB_IGNORE_RULES,
    });
  });

  test(
    "scans the row-actions menu and delete confirmation",
    RELEASE,
    async ({ page }) => {
      await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
      await openKnowledgeBasesRoute(page);
      await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      const rowActionsTrigger = page
        .getByTestId("kb-row-actions-trigger")
        .first();
      const viewChunksItem = page.getByRole("menuitem", {
        name: /view chunks/i,
      });

      await rowActionsTrigger.click();
      await expect(viewChunksItem).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.runA11yScan("kb-row-actions-open", {
        ignoreRules: KB_IGNORE_RULES,
      });

      await page.keyboard.press("Escape");
      await expect(viewChunksItem).toBeHidden({ timeout: TIMEOUTS.standard });
      await rowActionsTrigger.click();
      const deleteItem = page.getByRole("menuitem", { name: /^Delete$/ });
      await expect(deleteItem).toBeVisible({ timeout: TIMEOUTS.standard });

      await deleteItem.click();
      await expect(
        page.getByTestId("btn_delete_delete_confirmation_modal"),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.runA11yScan("kb-delete-modal-open", {
        ignoreRules: KB_IGNORE_RULES,
      });
    },
  );

  test("scans the detail drawer", RELEASE, async ({ page }) => {
    await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
    await mockIngestionRuns(page, []);
    await openKnowledgeBasesRoute(page);
    await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });

    await openKnowledgeBaseDrawer(page);
    await settleNetwork(page);
    await page.runA11yScan("kb-drawer-open", { ignoreRules: KB_IGNORE_RULES });
  });

  test(
    "scans the drawer with runs and ingestion run detail",
    RELEASE,
    async ({ page }) => {
      await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
      await mockIngestionRuns(page, [SEEDED_RUN]);
      await mockIngestionRunDetail(page, SEEDED_RUN_DETAIL);
      await openKnowledgeBasesRoute(page);
      await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await openKnowledgeBaseDrawer(page);
      await expect(page.getByText(/succeeded/i).first()).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await settleNetwork(page);
      await page.runA11yScan("kb-drawer-runs-populated", {
        ignoreRules: KB_IGNORE_RULES,
      });

      await page
        .getByText(/succeeded/i)
        .first()
        .click();
      await expect(page.getByTestId("run-detail-run-id")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await page.runA11yScan("kb-ingestion-run-detail", {
        ignoreRules: KB_IGNORE_RULES,
      });
    },
  );

  test("scans create-modal step 1 surfaces", RELEASE, async ({ page }) => {
    await openCreateModal(page);
    await settleNetwork(page);
    await page.runA11yScan("kb-upload-step-configuration", {
      ignoreRules: KB_IGNORE_RULES,
    });

    await expect(page.getByTestId("kb-chunk-size-input")).toBeVisible();
    await expect(page.getByTestId("kb-separator-input")).toBeVisible();
    await page.getByTestId("kb-browse-btn").click();
    await expect(
      page.getByRole("menuitem", { name: /upload files/i }),
    ).toBeVisible({ timeout: TIMEOUTS.standard });
    await page.runA11yScan("kb-upload-step-configuration-advanced", {
      ignoreRules: KB_IGNORE_RULES,
    });

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("kb-run-metadata-add")).toBeVisible();
    await page.getByTestId("kb-run-metadata-add").click();
    await expect(page.getByTestId("kb-run-metadata-key-0")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await expect(page.getByTestId("kb-run-metadata-value-0")).toBeVisible();
    await page.runA11yScan("kb-upload-metadata-add", {
      ignoreRules: KB_IGNORE_RULES,
    });
  });

  test("scans the review & build step (step 2)", RELEASE, async ({ page }) => {
    await page.route(KB_PREVIEW_GLOB, (route) =>
      route.fulfill({
        json: {
          files: [
            {
              preview_chunks: [
                {
                  content: "This is a previewed chunk of the uploaded file.",
                  char_count: 47,
                  start: 0,
                  end: 47,
                },
              ],
            },
          ],
        },
      }),
    );
    await openCreateModal(page);

    await page.getByTestId("kb-source-name-input").fill("review_kb");
    await page.locator("#file-input").setInputFiles(SAMPLE_FILE_PATH);

    await page.getByRole("button", { name: /next step/i }).click();
    await expect(
      page.getByRole("heading", { name: /review & build/i }),
    ).toBeVisible({ timeout: TIMEOUTS.standard });
    await expect(page.getByTestId("kb-create-button")).toBeVisible();
    await settleNetwork(page);
    await page.runA11yScan("kb-upload-step-review", {
      ignoreRules: KB_IGNORE_RULES,
    });
  });

  test("scans the no-search-results table", RELEASE, async ({ page }) => {
    await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
    await openKnowledgeBasesRoute(page);
    await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });

    await page.getByTestId("search-kb-input").fill("zzz-no-such-kb");
    await expect(page.getByText("Alpha Knowledge Base")).toBeHidden({
      timeout: TIMEOUTS.standard,
    });
    await settleNetwork(page);
    await page.runA11yScan("kb-no-search-results", {
      ignoreRules: KB_IGNORE_RULES,
    });
  });

  test(
    "scans the busy row-actions menu with stop ingestion",
    RELEASE,
    async ({ page }) => {
      await mockKnowledgeBases(page, SEEDED_STATUS_KNOWLEDGE_BASES);
      await openKnowledgeBasesRoute(page);
      await expect(page.getByText("Ingesting Knowledge Base")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      const busyRow = page.locator(".ag-row", {
        hasText: "Ingesting Knowledge Base",
      });
      await busyRow.getByTestId("kb-row-actions-trigger").first().click();
      await expect(
        page.getByRole("menuitem", { name: /stop ingestion/i }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.runA11yScan("kb-row-actions-busy", {
        ignoreRules: KB_IGNORE_RULES,
      });
    },
  );

  test("scans the drawer runs loading state", RELEASE, async ({ page }) => {
    await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
    const releaseRuns = await gateRoute(page, KB_RUNS_LIST_GLOB, {
      runs: [],
      total: 0,
      page: 1,
      limit: 10,
      total_pages: 0,
    });
    await openKnowledgeBasesRoute(page);
    await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });

    await openKnowledgeBaseDrawer(page);
    await expect(page.getByText(/loading runs/i)).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await page.runA11yScan("kb-drawer-runs-loading", {
      ignoreRules: KB_IGNORE_RULES,
    });

    releaseRuns();
    await settleNetwork(page);
  });

  test("scans the drawer runs error state", RELEASE, async ({ page }) => {
    page.allowFlowErrors();
    await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
    await page.route(KB_RUNS_LIST_GLOB, (route) =>
      route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Bad request" }),
      }),
    );
    await openKnowledgeBasesRoute(page);
    await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });

    await openKnowledgeBaseDrawer(page);
    await expect(page.getByText(/unable to load ingestion runs/i)).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await page.runA11yScan("kb-drawer-runs-error", {
      ignoreRules: KB_IGNORE_RULES,
    });
  });

  test("scans the add-sources modal", RELEASE, async ({ page }) => {
    await openAddSourcesModal(page);
    await expect(page.getByTestId("kb-source-name-input")).toBeDisabled();
    await settleNetwork(page);
    await page.runA11yScan("kb-add-sources-mode", {
      ignoreRules: KB_IGNORE_RULES,
    });
  });

  test(
    "scans the files panel and per-file metadata editor",
    RELEASE,
    async ({ page }) => {
      await openCreateModal(page);
      await attachFiles(page, [SAMPLE_FILE_PATH]);
      await settleNetwork(page);
      await page.runA11yScan("kb-upload-files-panel", {
        ignoreRules: KB_IGNORE_RULES,
      });

      const toggle = page.getByTestId("kb-file-metadata-toggle-0");
      await toggle.hover();
      await toggle.click();
      await expect(page.getByTestId("kb-file-metadata-editor-0")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await page.runA11yScan("kb-upload-per-file-metadata", {
        ignoreRules: KB_IGNORE_RULES,
      });
    },
  );

  test(
    "scans the embedding and db provider dropdowns",
    RELEASE,
    async ({ page }) => {
      await openCreateModal(page);

      await page.getByTestId("value-dropdown-kb-embedding-model").click();
      await expect(
        page.getByTestId("text-embedding-3-small-option"),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.runA11yScan("kb-upload-embedding-dropdown", {
        ignoreRules: KB_IGNORE_RULES,
      });

      await page.keyboard.press("Escape");
      await page.getByTestId("value-dropdown-kb-db-provider").click();
      await expect(page.getByTestId("chroma-provider-option")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await page.runA11yScan("kb-upload-db-provider-dropdown", {
        ignoreRules: KB_IGNORE_RULES,
      });
    },
  );

  test("scans the metadata validation error", RELEASE, async ({ page }) => {
    await openCreateModal(page);

    await page.getByTestId("kb-run-metadata-add").click();
    await page.getByTestId("kb-run-metadata-key-0").fill("BadKey");
    await page.getByTestId("kb-run-metadata-value-0").fill("value");
    await expect(page.getByTestId("kb-run-metadata-error-0")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await page.runA11yScan("kb-upload-metadata-error", {
      ignoreRules: KB_IGNORE_RULES,
    });
  });

  test("scans the review step with no files", RELEASE, async ({ page }) => {
    await openCreateModal(page);

    await page.getByTestId("kb-source-name-input").fill("review_kb");
    await page.getByRole("button", { name: /next step/i }).click();
    await expect(
      page.getByRole("heading", { name: /review & build/i }),
    ).toBeVisible({ timeout: TIMEOUTS.standard });
    await expect(page.getByText(/no files selected/i)).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await page.runA11yScan("kb-review-no-files", {
      ignoreRules: KB_IGNORE_RULES,
    });
  });

  test("scans the review preview loading state", RELEASE, async ({ page }) => {
    await openCreateModal(page);
    const releasePreview = await gateRoute(page, KB_PREVIEW_GLOB, {
      files: [{ preview_chunks: [] }],
    });

    await attachFiles(page, [SAMPLE_FILE_PATH]);
    await page.getByRole("button", { name: /next step/i }).click();
    await expect(page.getByText(/generating preview/i)).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await page.runA11yScan("kb-review-preview-loading", {
      ignoreRules: KB_IGNORE_RULES,
    });

    releasePreview();
    await settleNetwork(page);
  });

  test("scans the review preview error state", RELEASE, async ({ page }) => {
    page.allowFlowErrors();
    await openCreateModal(page);
    await page.route(KB_PREVIEW_GLOB, (route) =>
      route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Bad request" }),
      }),
    );

    await attachFiles(page, [SAMPLE_FILE_PATH]);
    await page.getByRole("button", { name: /next step/i }).click();
    await expect(page.getByText(/could not generate preview/i)).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await page.runA11yScan("kb-review-preview-error", {
      ignoreRules: KB_IGNORE_RULES,
    });
  });

  test(
    "scans the review multi-file preview switcher",
    RELEASE,
    async ({ page }) => {
      await page.route(KB_PREVIEW_GLOB, (route) =>
        route.fulfill({
          json: {
            files: [
              {
                preview_chunks: [
                  {
                    content: "First previewed chunk of the uploaded file.",
                    char_count: 43,
                    start: 0,
                    end: 43,
                  },
                  {
                    content: "Second previewed chunk of the uploaded file.",
                    char_count: 44,
                    start: 44,
                    end: 88,
                  },
                ],
              },
            ],
          },
        }),
      );
      await openCreateModal(page);
      await attachFiles(page, [SAMPLE_FILE_PATH, SAMPLE_FILE_PATH_2]);

      await page.getByRole("button", { name: /next step/i }).click();
      await expect(
        page.getByRole("heading", { name: /review & build/i }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });

      await page
        .getByRole("button", { name: "resume.txt", exact: true })
        .click();
      await expect(
        page.getByRole("menuitem", { name: /test-file\.txt/i }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.runA11yScan("kb-review-multifile", {
        ignoreRules: KB_IGNORE_RULES,
      });
    },
  );
});

test.describe("knowledge base chunks page accessibility", () => {
  for (const scenario of KB_CHUNKS_SCENARIOS) {
    test(`scans the ${scenario.name}`, RELEASE, async ({ page }) => {
      await scenario.run(page);
    });
  }

  test("scans the chunks loading state", RELEASE, async ({ page }) => {
    const releaseChunks = await gateRoute(
      page,
      KB_CHUNKS_GLOB,
      SEEDED_CHUNKS_RESPONSE,
    );
    await awaitBootstrapTest(page, { skipModal: true });
    await page.goto("/assets/knowledge-bases/alpha_kb/chunks");
    await disableAnimations(page);

    await expect(page.getByTestId("source-chunks-wrapper")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await expect(page.getByText(/loading chunks/i)).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await page.runA11yScan("kbchunks-loading", {
      ignoreRules: KB_IGNORE_RULES,
    });

    releaseChunks();
    await settleNetwork(page);
  });

  test("scans the chunks fetch error state", RELEASE, async ({ page }) => {
    page.allowFlowErrors();
    await page.route(KB_CHUNKS_GLOB, (route) =>
      route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Bad request" }),
      }),
    );
    await openChunksRoute(page, "alpha_kb");

    await expect(page.getByText(/failed to load chunks/i)).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await page.runA11yScan("kbchunks-error", { ignoreRules: KB_IGNORE_RULES });
  });

  test("scans the source-type filter dropdown", RELEASE, async ({ page }) => {
    await mockChunks(page, SEEDED_CHUNKS_RESPONSE);
    await openChunksRoute(page, "alpha_kb");
    await expect(page.getByTestId("chunks-source-type-filter")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });

    await page.getByTestId("chunks-source-type-filter").click();
    await expect(
      page.getByRole("option", { name: /file upload/i }),
    ).toBeVisible({ timeout: TIMEOUTS.standard });
    await page.runA11yScan("kbchunks-source-type-filter-open", {
      ignoreRules: KB_IGNORE_RULES,
    });
  });

  test(
    "scans the metadata filter popover and comboboxes",
    RELEASE,
    async ({ page }) => {
      await mockChunks(page, SEEDED_CHUNKS_RESPONSE);
      await mockMetadataKeys(page, { team: ["docs", "eng"] });
      await openChunksRoute(page, "alpha_kb");
      await expect(page.getByTestId("chunks-metadata-add-filter")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await page.getByTestId("chunks-metadata-add-filter").click();
      await expect(
        page.getByTestId("chunks-metadata-filter-submit"),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.runA11yScan("kbchunks-filter-open", {
        ignoreRules: KB_IGNORE_RULES,
      });

      await page.getByTestId("chunks-metadata-filter-key").click();
      await expect(
        page.getByTestId("chunks-metadata-filter-key-option-team"),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.runA11yScan("kbchunks-metadata-key-combobox", {
        ignoreRules: KB_IGNORE_RULES,
      });

      await page.getByTestId("chunks-metadata-filter-key-option-team").click();
      await page.getByTestId("chunks-metadata-filter-value").click();
      await page
        .getByTestId("chunks-metadata-filter-value-input")
        .fill("customval");
      await expect(
        page.getByTestId("chunks-metadata-filter-value-custom"),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.runA11yScan("kbchunks-metadata-value-combobox", {
        ignoreRules: KB_IGNORE_RULES,
      });
    },
  );

  test("scans the applied metadata filter chips", RELEASE, async ({ page }) => {
    await mockChunks(page, SEEDED_CHUNKS_RESPONSE);
    await mockMetadataKeys(page, { team: ["docs", "eng"] });
    await openChunksRoute(page, "alpha_kb");
    await expect(page.getByTestId("chunks-metadata-add-filter")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });

    await page.getByTestId("chunks-metadata-add-filter").click();
    await page.getByTestId("chunks-metadata-filter-key").click();
    await page.getByTestId("chunks-metadata-filter-key-option-team").click();
    await page.getByTestId("chunks-metadata-filter-value").click();
    await page.getByTestId("chunks-metadata-filter-value-option-docs").click();
    await page.getByTestId("chunks-metadata-filter-submit").click();

    await expect(page.getByTestId("chunks-metadata-filter-chips")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await settleNetwork(page);
    await page.runA11yScan("kbchunks-filter-chips", {
      ignoreRules: KB_IGNORE_RULES,
    });
  });

  test("scans an expanded chunk card", RELEASE, async ({ page }) => {
    const longContent =
      "Langflow lets you compose AI workflows visually. ".repeat(12);
    await mockChunks(page, {
      chunks: [
        {
          id: "chunk-long",
          content: longContent,
          char_count: longContent.length,
          metadata: {
            file_name: "handbook.txt",
            source_metadata: JSON.stringify({ team: "docs" }),
          },
        },
      ],
      total: 1,
      page: 1,
      limit: 10,
      total_pages: 1,
    });
    await openChunksRoute(page, "alpha_kb");
    const card = page.getByText(/langflow lets you compose ai workflows/i);
    await expect(card.first()).toBeVisible({ timeout: TIMEOUTS.standard });

    await card.first().click();
    await settleNetwork(page);
    await page.runA11yScan("kbchunks-card-expanded", {
      ignoreRules: KB_IGNORE_RULES,
    });
  });
});
