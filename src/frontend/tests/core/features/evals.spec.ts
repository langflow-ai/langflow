import fs from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.skip(
  process.env.LANGFLOW_FEATURE_EVALS !== "true",
  "Requires LANGFLOW_FEATURE_EVALS=true",
);

// A no-LLM echo flow: each row's answer is its own input, so the run is free and deterministic.
const ECHO_FLOW = JSON.parse(
  fs.readFileSync(
    path.join(__dirname, "../../assets/a2a", "echo-agent.json"),
    "utf-8",
  ),
);

async function seedEchoFlow(page: Page, name: string): Promise<string> {
  return page.evaluate(
    async ({ flow, name }) => {
      const res = await fetch("/api/v1/flows/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...flow, name }),
      });
      if (!res.ok) throw new Error(`seed flow failed: ${res.status}`);
      return (await res.json()).id as string;
    },
    { flow: ECHO_FLOW, name },
  );
}

// AG Grid names the grid and makes a cell tabbable once it is ready; scan after that.
async function waitForGridReady(page: Page) {
  await page.waitForFunction(() => {
    const grid = document.querySelector('[role="treegrid"]');
    return (
      Boolean(grid?.getAttribute("aria-label")) &&
      Boolean(
        grid?.querySelector(
          '[role="rowgroup"] [tabindex="0"], [role="rowgroup"][tabindex="0"]',
        ),
      )
    );
  });
}

async function addItem(page: Page, input: string, expected: string) {
  await page.getByTestId("add-item-button").click();
  await page.getByTestId("item-input").fill(input);
  await page.getByTestId("item-expected").fill(expected);
  await page.getByTestId("item-save").click();
  await expect(page.getByTestId("item-save")).toBeHidden();
}

test(
  "user creates a dataset, evaluates a flow and re-runs it",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const suffix = Date.now().toString(36);
    const datasetName = `support-qa-${suffix}`;
    await awaitBootstrapTest(page, { skipModal: true });
    const flowId = await seedEchoFlow(page, `Evals echo ${suffix}`);

    await page.getByTestId("sidebar-datasets").click();
    await expect(page.getByTestId("datasets-title")).toBeVisible();
    await page.runA11yScan("evals-datasets-list");
    await page.getByTestId("new-dataset-button").click();
    await page.getByTestId("dataset-name-input").fill(datasetName);
    await page.getByTestId("dataset-create-submit").click();

    await expect(page.getByTestId("dataset-detail-title")).toHaveText(
      datasetName,
    );
    await addItem(page, "hello", "hello");
    await addItem(page, "world", "something else");
    await expect(page.locator(".ag-center-cols-container .ag-row")).toHaveCount(
      2,
    );
    await waitForGridReady(page);
    await page.runA11yScan("evals-dataset-detail");

    await page.getByTestId("csv-import-button").click();
    await page.runA11yScan("evals-csv-import-empty");
    await page.setInputFiles('[data-testid="csv-file-input"]', {
      name: "extra.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("question;answer\nPing;Ping\n;skipped\n"),
    });
    await expect(page.getByTestId("csv-import-submit")).toBeEnabled();
    await page.runA11yScan("evals-csv-import-preview");
    await page.getByTestId("csv-import-submit").click();
    await expect(page.getByTestId("csv-import-result")).toHaveText(
      "1 row imported",
    );
    await page.getByTestId("csv-import-submit").click();
    await expect(page.locator(".ag-center-cols-container .ag-row")).toHaveCount(
      3,
    );

    await page.goto(`/flow/${flowId}`);
    await page.getByTestId("evaluate-btn-flow").click();
    await page.getByTestId("evaluate-dataset").click();
    await page.getByRole("option", { name: new RegExp(datasetName) }).click();
    await expect(page.getByTestId("evaluate-estimate")).toBeVisible();
    await page.runA11yScan("evals-evaluate-modal");
    await page.getByTestId("evaluate-submit").click();

    await expect(page.getByTestId("evaluation-detail-title")).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByTestId("run-status-completed")).toBeVisible({
      timeout: 60000,
    });
    await expect(page.locator(".ag-center-cols-container .ag-row")).toHaveCount(
      3,
    );
    await expect(page.getByTestId("results-filter-passed")).toContainText("2");
    await waitForGridReady(page);
    await page.runA11yScan("evals-run-results");
    await page.locator(".ag-center-cols-container .ag-row").first().click();
    await expect(page.getByRole("dialog")).toContainText("Row 1");
    await page.runA11yScan("evals-result-detail");
    await page.keyboard.press("Escape");

    await page.getByTestId("rerun-button").click();
    await page.getByTestId("rerun-latest").click();
    await expect(page.getByTestId("run-row")).toHaveCount(2, {
      timeout: 30000,
    });
    await expect(page.getByTestId("run-status-completed")).toHaveCount(2, {
      timeout: 60000,
    });

    // A shared or bookmarked run link must open the run, not bounce to /flows.
    await page.reload();
    await expect(page.getByTestId("evaluation-detail-title")).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByTestId("run-row")).toHaveCount(2);

    await page.getByTestId("sidebar-evaluations").click();
    await expect(page.getByTestId("evaluations-title")).toBeVisible();
    await expect(page.getByTestId("evaluation-detail-title")).toBeHidden();
    await expect(
      page.locator(".ag-center-cols-container .ag-row").first(),
    ).toBeVisible();
    await waitForGridReady(page);
    await page.runA11yScan("evals-evaluations-list");

    await page.getByTestId("new-evaluation-button").click();
    await page.getByTestId("evaluate-flow").click();
    await page.getByTestId("evaluate-flow-search").fill(`Evals echo ${suffix}`);
    await page.getByRole("option", { name: `Evals echo ${suffix}` }).click();
    await page.getByTestId("evaluate-dataset").click();
    await page.getByRole("option", { name: new RegExp(datasetName) }).click();
    await expect(page.getByTestId("evaluate-estimate")).toBeVisible();
    await page.runA11yScan("evals-new-evaluation-modal");
    await page.getByTestId("evaluate-submit").click();
    await expect(page.getByTestId("evaluation-detail-title")).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByTestId("run-status-completed")).toBeVisible({
      timeout: 60000,
    });
  },
);
