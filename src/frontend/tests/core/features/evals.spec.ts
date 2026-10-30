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

    await page.getByTestId("sidebar-evaluations").click();
    await page.getByTestId("evals-tab-datasets").click();
    await expect(page.getByTestId("datasets-title")).toBeVisible();
    await page.runA11yScan("evals-datasets-list");
    // One click creates the dataset and opens it with its name ready to type.
    await page.getByTestId("new-dataset-button").click();
    await page.getByTestId("dataset-name-input").fill(datasetName);
    await page.getByTestId("dataset-name-input").press("Enter");

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

    await page.setInputFiles('[data-testid="csv-import-button-input"]', {
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

test(
  "user adds an example dataset in one click",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });
    await page.getByTestId("sidebar-evaluations").click();
    await page.getByTestId("evals-tab-datasets").click();
    await expect(page.getByTestId("datasets-title")).toBeVisible();

    const fromEmptyState = page.getByTestId("dataset-example-support-triage");
    if (await fromEmptyState.isVisible()) {
      await page.runA11yScan("evals-datasets-empty-examples");
      await fromEmptyState.click();
    } else {
      await page.getByTestId("dataset-examples-menu").click();
      await page.getByTestId("dataset-example-menu-support-triage").click();
    }

    await expect(page.getByTestId("dataset-detail-title")).toContainText(
      "Support ticket triage",
    );
    await expect(page.getByText(/^12 items · /)).toBeVisible();
  },
);

test(
  "user compares two model versions of a flow and re-runs the comparison",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const suffix = Date.now().toString(36);
    await awaitBootstrapTest(page, { skipModal: true });
    // The echo flow with a model picker the run never calls: versions are free and deterministic.
    const withPicker = structuredClone(ECHO_FLOW);
    const input = withPicker.data.nodes.find(
      (node: { data: { type: string } }) => node.data.type === "ChatInput",
    );
    input.data.node.template.model = {
      type: "model",
      display_name: "Language Model",
      model_type: "language",
      value: [{ name: "gpt-4o-mini", provider: "OpenAI", metadata: {} }],
      show: true,
      advanced: false,
    };
    const { flowId, datasetName } = await page.evaluate(
      async ({ flow, suffix }) => {
        const post = async (url: string, body: unknown) => {
          const res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });
          if (!res.ok) throw new Error(`${url} failed: ${res.status}`);
          return res.json();
        };
        const created = await post("/api/v1/flows/", {
          ...flow,
          name: `Evals compare ${suffix}`,
        });
        const dataset = await post("/api/v1/datasets/", {
          name: `compare-${suffix}`,
        });
        await post(`/api/v1/datasets/${dataset.id}/items`, {
          items: [
            { input: "hello", expected_output: "hello" },
            { input: "world", expected_output: "other" },
          ],
        });
        return { flowId: created.id as string, datasetName: dataset.name };
      },
      { flow: withPicker, suffix },
    );

    await page.goto(`/flow/${flowId}`);
    await page.getByTestId("evaluate-btn-flow").click();
    await page.getByTestId("evaluate-dataset").click();
    await page.getByRole("option", { name: new RegExp(datasetName) }).click();
    await page.getByTestId("evaluate-models").click();
    await page.getByTestId("model-version-add").click();
    await expect(page.getByTestId("model-version-1")).toBeVisible();
    await expect(page.getByTestId("evaluate-submit")).toContainText("2");
    await expect(page.getByTestId("evaluate-estimate")).toBeVisible();
    await page.runA11yScan("evals-evaluate-compare");
    await page.getByTestId("evaluate-submit").click();
    // The estimate counts the picker as a model call, so the run asks once more.
    await expect(page.getByTestId("confirm-run-submit")).toContainText(
      /confirm/i,
    );
    await page.getByTestId("confirm-run-submit").click();

    await expect(page.getByTestId("model-comparison")).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByTestId("run-status-completed")).toHaveCount(2, {
      timeout: 60000,
    });
    const rows = page.getByTestId("comparison-row");
    await expect(rows).toHaveCount(2);
    await expect(page.getByTestId("comparison-most-accurate")).toContainText(
      "50%",
    );
    await page.runA11yScan("evals-model-comparison");
    await rows.nth(1).getByRole("button").click();
    await expect(rows.nth(1)).toHaveAttribute("aria-selected", "true");

    await page.getByTestId("rerun-button").click();
    await page.getByTestId("rerun-comparison").click();
    await page.getByTestId("confirm-run-submit").click();
    await expect(page.getByTestId("run-row")).toHaveCount(4, {
      timeout: 60000,
    });
    await expect(page.getByTestId("run-status-completed")).toHaveCount(4, {
      timeout: 60000,
    });
  },
);
