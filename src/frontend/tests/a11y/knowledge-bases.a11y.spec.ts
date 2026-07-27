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
      await page.runA11yScan("kb-empty");
    },
  },
  {
    name: "populated table",
    run: async (page) => {
      await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
      await openKnowledgeBasesRoute(page);
      await expect(page.getByTestId("search-kb-input")).toBeVisible();
      await expect(
        page.getByRole("textbox", { name: /search knowledge bases/i }),
      ).toBeVisible();
      await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await settleNetwork(page);
      await page.runA11yScan("kb-populated");
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
      await page.runA11yScan("kb-row-status-variants");
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
        page.getByRole("textbox", { name: /search chunks/i }),
      ).toBeVisible();
      await expect(
        page.getByRole("combobox", { name: /filter by source type/i }),
      ).toBeVisible();
      await expect(
        page.getByText(/langflow lets you compose ai workflows/i),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await settleNetwork(page);
      await page.runA11yScan("kbchunks-populated");
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
      await page.runA11yScan("kbchunks-empty");
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
      await page.runA11yScan("kbchunks-pagination");
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
    await page.runA11yScan("kb-loading");

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
    await page.runA11yScan("kb-error");
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
    await page.runA11yScan("kb-selection-mode");

    await deleteSelected.click();
    await expect(
      page.getByTestId("btn_delete_delete_confirmation_modal"),
    ).toBeVisible({ timeout: TIMEOUTS.standard });
    await page.runA11yScan("kb-bulk-delete-modal-open");

    await page.keyboard.press("Escape");
    await expect(
      page.getByTestId("btn_cancel_delete_confirmation_modal"),
    ).toBeHidden({ timeout: TIMEOUTS.standard });
    await expect(deleteSelected).toBeFocused({ timeout: TIMEOUTS.standard });
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
      await page.runA11yScan("kb-row-actions-open");

      // The a11y scan drops the open menu, so it must be reopened to reach the
      // Delete item. Reopening a Radix menu is a toggle click, which can race
      // the previous close, so poll: click the trigger until Delete renders.
      await page.keyboard.press("Escape");
      await expect(viewChunksItem).toBeHidden({ timeout: TIMEOUTS.standard });

      const deleteItem = page.getByRole("menuitem", { name: /^Delete$/ });
      await expect(async () => {
        await rowActionsTrigger.click();
        await expect(deleteItem).toBeVisible({ timeout: TIMEOUTS.short });
      }).toPass({ timeout: TIMEOUTS.standard });

      await deleteItem.click();
      await expect(
        page.getByTestId("btn_delete_delete_confirmation_modal"),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.runA11yScan("kb-delete-modal-open");

      await page.keyboard.press("Escape");
      await expect(
        page.getByTestId("btn_cancel_delete_confirmation_modal"),
      ).toBeHidden({ timeout: TIMEOUTS.standard });
      await expect(rowActionsTrigger).toBeFocused({
        timeout: TIMEOUTS.standard,
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
    const drawer = page.getByTestId("knowledge-base-drawer");
    await expect(drawer).toBeVisible({ timeout: TIMEOUTS.standard });
    await expect(drawer).toHaveAttribute("role", "region");
    await expect(
      page.getByRole("button", { name: /close details panel/i }),
    ).toBeFocused({ timeout: TIMEOUTS.standard });
    await settleNetwork(page);
    await page.runA11yScan("kb-drawer-open");

    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden({ timeout: TIMEOUTS.standard });
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
      const runButton = page
        .getByRole("button", { name: /succeeded/i })
        .first();
      await expect(runButton).toBeVisible({ timeout: TIMEOUTS.standard });
      await settleNetwork(page);
      await page.runA11yScan("kb-drawer-runs-populated");

      await runButton.click();
      const runDialog = page.getByRole("dialog", {
        name: /ingestion run detail/i,
      });
      await expect(runDialog).toBeVisible({ timeout: TIMEOUTS.standard });
      await expect(page.getByTestId("run-detail-run-id")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      const closeRun = page.getByRole("button", { name: /close run detail/i });
      await expect(closeRun).toBeFocused({ timeout: TIMEOUTS.standard });
      await page.runA11yScan("kb-ingestion-run-detail");

      await page.keyboard.press("Tab");
      await expect(closeRun).toBeFocused();
      await page.keyboard.press("Escape");
      await expect(runDialog).toBeHidden({ timeout: TIMEOUTS.standard });
      await expect(runButton).toBeFocused({ timeout: TIMEOUTS.standard });
    },
  );

  test("scans create-modal step 1 surfaces", RELEASE, async ({ page }) => {
    await openCreateModal(page);
    await expect(
      page.getByRole("combobox", { name: /embedding model/i }),
    ).toBeVisible({ timeout: TIMEOUTS.standard });
    await expect(
      page.getByRole("combobox", { name: /db provider/i }),
    ).toBeVisible();
    await settleNetwork(page);
    await page.runA11yScan("kb-upload-step-configuration");

    await expect(page.getByTestId("kb-chunk-size-input")).toBeVisible();
    await expect(page.getByTestId("kb-separator-input")).toBeVisible();
    await page.getByTestId("kb-browse-btn").click();
    await expect(
      page.getByRole("menuitem", { name: /upload files/i }),
    ).toBeVisible({ timeout: TIMEOUTS.standard });
    await page.runA11yScan("kb-upload-step-configuration-advanced");

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("kb-run-metadata-add")).toBeVisible();
    await page.getByTestId("kb-run-metadata-add").click();
    await expect(page.getByTestId("kb-run-metadata-key-0")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await expect(page.getByTestId("kb-run-metadata-value-0")).toBeVisible();
    await page.runA11yScan("kb-upload-metadata-add");

    const addKnowledge = page.getByRole("button", { name: /add knowledge/i });
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden({
      timeout: TIMEOUTS.standard,
    });
    await expect(addKnowledge).toBeFocused({ timeout: TIMEOUTS.standard });
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
    await page.runA11yScan("kb-upload-step-review");
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
    await page.runA11yScan("kb-no-search-results");
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
      await page.runA11yScan("kb-row-actions-busy");
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
    await page.runA11yScan("kb-drawer-runs-loading");

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
    await page.runA11yScan("kb-drawer-runs-error");
  });

  test("scans the add-sources modal", RELEASE, async ({ page }) => {
    await openAddSourcesModal(page);
    await expect(page.getByTestId("kb-source-name-input")).toBeDisabled();
    await settleNetwork(page);
    await page.runA11yScan("kb-add-sources-mode");
  });

  test(
    "scans the files panel and per-file metadata editor",
    RELEASE,
    async ({ page }) => {
      await openCreateModal(page);
      await attachFiles(page, [SAMPLE_FILE_PATH]);
      await settleNetwork(page);
      await page.runA11yScan("kb-upload-files-panel");

      const toggle = page.getByTestId("kb-file-metadata-toggle-0");
      await toggle.hover();
      await toggle.click();
      await expect(page.getByTestId("kb-file-metadata-editor-0")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await page.runA11yScan("kb-upload-per-file-metadata");
    },
  );

  test(
    "scans the embedding and db provider dropdowns",
    RELEASE,
    async ({ page }) => {
      await openCreateModal(page);

      await expect(
        page.getByRole("combobox", { name: /embedding model/i }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.getByRole("combobox", { name: /embedding model/i }).click();
      await expect(
        page.getByTestId("OpenAI-text-embedding-3-small-option"),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await expect(page.getByTestId("manage-model-providers")).toBeVisible();
      await page.runA11yScan("kb-upload-embedding-dropdown");

      await page.getByTestId("manage-model-providers").click();
      const openaiProvider = page.getByTestId("provider-item-OpenAI");
      await expect(openaiProvider).toBeVisible({ timeout: TIMEOUTS.standard });
      await openaiProvider.focus();
      await expect(openaiProvider).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(openaiProvider).toHaveAttribute("aria-pressed", "true");
      await page.runA11yScan("kb-upload-manage-providers");

      await page.keyboard.press("Escape");
      await expect(openaiProvider).toBeHidden({ timeout: TIMEOUTS.standard });

      await page.getByRole("combobox", { name: /db provider/i }).click();
      await expect(page.getByTestId("chroma-provider-option")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await page.runA11yScan("kb-upload-db-provider-dropdown");
    },
  );

  test("scans the metadata validation error", RELEASE, async ({ page }) => {
    await openCreateModal(page);

    await page.getByTestId("kb-run-metadata-add").click();
    const keyInput = page.getByTestId("kb-run-metadata-key-0");
    await keyInput.fill("BadKey");
    await page.getByTestId("kb-run-metadata-value-0").fill("value");
    const error = page.getByTestId("kb-run-metadata-error-0");
    await expect(error).toBeVisible({ timeout: TIMEOUTS.standard });
    await expect(error).toHaveAttribute("role", "alert");
    await expect(keyInput).toHaveAttribute("aria-invalid", "true");
    await expect(keyInput).toHaveAttribute(
      "aria-describedby",
      "kb-run-metadata-error-0",
    );
    await page.runA11yScan("kb-upload-metadata-error");
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
    await page.runA11yScan("kb-review-no-files");
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
    await page.runA11yScan("kb-review-preview-loading");

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
    await page.runA11yScan("kb-review-preview-error");
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
      await page.runA11yScan("kb-review-multifile");
    },
  );

  test("scans populated table on mobile width", RELEASE, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
    await openKnowledgeBasesRoute(page);
    await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await settleNetwork(page);
    await page.runA11yScan("kb-mobile-data-rich");
  });

  test(
    "opens row actions menu with the keyboard and restores focus on close",
    RELEASE,
    async ({ page }) => {
      await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
      await openKnowledgeBasesRoute(page);
      await disableAnimations(page);
      await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      // Focus the actions cell itself (not an inner button) so Enter is handled
      // by onCellKeyDown — same pattern as files/api-keys (WCAG 2.1.1).
      const actionsCell = page
        .locator(
          '.ag-center-cols-container [role="gridcell"][col-id="actions"]',
        )
        .first();
      await expect(actionsCell).toBeVisible();
      await actionsCell.evaluate((element) => {
        (element as HTMLElement).focus();
      });
      await expect
        .poll(async () =>
          page.evaluate(() => document.activeElement?.getAttribute("col-id")),
        )
        .toBe("actions");

      // Enter on the actions cell opens the dropdown (WCAG 2.1.1).
      await page.keyboard.press("Enter");
      await expect(page.getByRole("menu")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      // Escape closes and returns focus to the (real button) trigger.
      await page.keyboard.press("Escape");
      await expect(page.getByRole("menu")).toBeHidden({
        timeout: TIMEOUTS.standard,
      });
      const focusedName = await page.evaluate(
        () => document.activeElement?.getAttribute("aria-label") ?? "",
      );
      expect(focusedName).toMatch(/Actions for/);
    },
  );

  test(
    "shows a visible focus ring on grid cells for keyboard but not mouse",
    RELEASE,
    async ({ page }) => {
      await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
      await openKnowledgeBasesRoute(page);
      await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      // WCAG 2.4.7: keyboard navigation must show a visible focus ring. The
      // borderless knowledge table hides AG Grid's default cell outline, so this
      // guards the :focus-visible restore on .ag-knowledge-table.
      await page.getByTestId("search-kb-input").focus();
      for (let i = 0; i < 12; i++) {
        const onCell = await page.evaluate(() =>
          document.activeElement?.classList.contains("ag-cell"),
        );
        if (onCell) break;
        await page.keyboard.press("Tab");
      }
      const keyboardFocus = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el?.classList.contains("ag-cell")) return null;
        const cs = getComputedStyle(el);
        return {
          style: cs.outlineStyle,
          hasWidth: parseFloat(cs.outlineWidth) > 0,
        };
      });
      expect(keyboardFocus).toEqual({ style: "solid", hasWidth: true });

      // A mouse click resolves to :focus (not :focus-visible), so no ring shows.
      await page
        .locator(
          '.ag-center-cols-container .ag-row [role="gridcell"][col-id="size"]',
        )
        .first()
        .click();
      const mouseOutlineStyle = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        return el ? getComputedStyle(el).outlineStyle : null;
      });
      expect(mouseOutlineStyle).toBe("none");
    },
  );

  test(
    "exits the table with a single Tab from the last cell",
    RELEASE,
    async ({ page }) => {
      await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
      await openKnowledgeBasesRoute(page);
      await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      // Focus the cell chrome (not an inner button) so Tab is handled by the
      // grid's tabToNextCell hook rather than native in-cell button tabbing.
      // Use the last row so Tab exits the grid instead of moving to the next row.
      const lastCell = page
        .locator(
          '.ag-center-cols-container [role="gridcell"][col-id="actions"]',
        )
        .last();
      await expect(lastCell).toBeVisible();
      await lastCell.evaluate((element) => {
        (element as HTMLElement).focus();
      });

      await page.keyboard.press("Tab");
      await page.waitForTimeout(50);

      const activeElement = await page.evaluate(() => {
        const element = document.activeElement as HTMLElement | null;
        return {
          tagName: element?.tagName.toLowerCase() ?? "",
          testId: element?.getAttribute("data-testid") ?? null,
          role: element?.getAttribute("role") ?? null,
          isGridCell: element?.getAttribute("role") === "gridcell",
          className: String(element?.className ?? ""),
        };
      });

      expect(activeElement.isGridCell, "focus should leave the grid body").toBe(
        false,
      );
      expect(
        activeElement.tagName,
        "a single Tab should reach the next control, not dead-stop on <body>",
      ).not.toBe("body");
    },
  );

  test(
    "re-enters the table on reverse tab without trapping on body",
    RELEASE,
    async ({ page }) => {
      await mockKnowledgeBases(page, SEEDED_KNOWLEDGE_BASES);
      await openKnowledgeBasesRoute(page);
      await expect(page.getByText("Alpha Knowledge Base")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      // Enter the grid from the search field (the control immediately before it),
      // then Shift+Tab back out. Reverse tabbing must not trap by oscillating
      // onto <body> (WCAG 2.1.2) — the regression an inert/disabled pagination
      // panel caused on other AG Grid pages.
      await page.getByTestId("search-kb-input").focus();

      let enteredGrid = false;
      for (let index = 0; index < 12; index += 1) {
        await page.keyboard.press("Tab");
        await page.waitForTimeout(20);
        enteredGrid = await page.evaluate(() =>
          Boolean(
            document.activeElement?.closest(
              '[role="treegrid"], .ag-root-wrapper',
            ),
          ),
        );
        if (enteredGrid) break;
      }
      expect(enteredGrid, "Tab from search should enter the data table").toBe(
        true,
      );

      const escaped: boolean[] = [];
      for (let index = 0; index < 6; index += 1) {
        await page.keyboard.press("Shift+Tab");
        await page.waitForTimeout(40);
        const snapshot = await page.evaluate(() => {
          const element = document.activeElement as HTMLElement | null;
          return {
            tagName: element?.tagName.toLowerCase() ?? "",
            testId: element?.getAttribute("data-testid") ?? null,
            inGrid: Boolean(
              element?.closest('[role="treegrid"], .ag-root-wrapper'),
            ),
          };
        });
        escaped.push(snapshot.tagName !== "body");
        // Once we're back on the search field, reverse entry succeeded.
        if (snapshot.testId === "search-kb-input") break;
      }

      expect(
        escaped.every(Boolean),
        "reverse tab must never land on <body>",
      ).toBe(true);
      expect(
        escaped.some(Boolean),
        "reverse tab must progress without a keyboard trap",
      ).toBe(true);
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
    await page.runA11yScan("kbchunks-loading");

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
    await page.runA11yScan("kbchunks-error");
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
    await page.runA11yScan("kbchunks-source-type-filter-open");
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
      await page.runA11yScan("kbchunks-filter-open");

      await page.getByTestId("chunks-metadata-filter-key").click();
      await expect(
        page.getByTestId("chunks-metadata-filter-key-option-team"),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.runA11yScan("kbchunks-metadata-key-combobox");

      await page.getByTestId("chunks-metadata-filter-key-option-team").click();
      await page.getByTestId("chunks-metadata-filter-value").click();
      await page
        .getByTestId("chunks-metadata-filter-value-input")
        .fill("customval");
      await expect(
        page.getByTestId("chunks-metadata-filter-value-custom"),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await page.runA11yScan("kbchunks-metadata-value-combobox");
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
    await page.runA11yScan("kbchunks-filter-chips");
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
    await page.runA11yScan("kbchunks-card-expanded");
  });
});
