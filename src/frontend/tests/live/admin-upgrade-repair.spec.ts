import { readFile } from "node:fs/promises";
import path from "node:path";
import type {
  RepairPreview,
  ReportDetail,
} from "../../src/controllers/API/queries/upgrade-reports";
import type { APIClassType } from "../../src/types/api";
import { expect, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";

// Run only against an isolated backend. This journey enables shared maintenance.
const routePath = "/settings/upgrade-reports";

test(
  "repairs a stored flow through the real report workflow",
  { tag: ["@release", "@database"] },
  async ({ page }) => {
    const login = await page.request.get("/api/v1/auto_login");
    expect(login.ok()).toBeTruthy();
    const headers = {
      Authorization: `Bearer ${(await login.json()).access_token}`,
    };
    const index: { entries: [string, Record<string, APIClassType>][] } =
      JSON.parse(
        await readFile(
          path.resolve(
            __dirname,
            "../../../lfx/src/lfx/_assets/component_index.json",
          ),
          "utf8",
        ),
      );
    const current = index.entries.find(([name]) => name === "input_output")?.[1]
      .ChatInput;
    if (!current)
      throw new Error("Chat Input is missing from the component index");
    const saved = structuredClone(current);
    saved.template.code.value += "\n# Previous installed component revision\n";
    saved.template.input_value.value = "Keep this saved input";
    const graph = {
      nodes: [
        {
          id: "ChatInput-upgrade-qa",
          type: "genericNode",
          position: { x: 0, y: 0 },
          data: { id: "ChatInput-upgrade-qa", type: "ChatInput", node: saved },
        },
      ],
      edges: [],
    };
    const created = await page.request.post("/api/v1/flows/", {
      headers,
      data: { name: `Upgrade QA ${Date.now()}`, data: graph },
    });
    expect(created.ok()).toBeTruthy();
    const flow = await created.json();
    try {
      await awaitBootstrapTest(page, {
        skipModal: true,
        seedFlowIfEmpty: false,
      });
      const document: ReportDetail["document"] = JSON.parse(
        await readFile(
          path.resolve(
            __dirname,
            "../../../backend/tests/unit/api/v1/fixtures/upgrade-report-v1.json",
          ),
          "utf8",
        ),
      );
      document.generated_at = new Date().toISOString();
      document.summary.flows = { ok: 0, warn: 1, fail: 0 };
      document.errors = [];
      document.flows = [
        {
          ...document.flows[0],
          id: flow.id,
          flow_id: flow.id,
          name: flow.name,
          status: "warn",
        },
      ];
      await page.goto(routePath);
      await page.getByLabel("Checker report file").setInputFiles({
        name: "real-repair-report.json",
        mimeType: "application/json",
        buffer: Buffer.from(JSON.stringify(document)),
      });
      const imported = page.waitForResponse(
        (response) =>
          response.url().endsWith("/api/v1/upgrade-reports") &&
          response.request().method() === "POST",
      );
      await page
        .getByRole("button", { name: "Import report", exact: true })
        .click();
      const importedResponse = await imported;
      expect(importedResponse.ok(), await importedResponse.text()).toBeTruthy();
      await expect(
        page.getByRole("heading", {
          name: "Review required before upgrading",
          exact: true,
        }),
      ).toBeVisible();
      await page
        .getByText("How to enable maintenance", { exact: true })
        .click();
      await expect(
        page.getByRole("link", { name: "Maintenance instructions" }),
      ).toHaveAttribute("href", "https://docs.langflow.org/maintenance-mode");
      const maintenanceCommands = page.locator("code").filter({
        hasText: "langflow maintenance on",
      });
      await expect(maintenanceCommands).toContainText(
        'langflow maintenance on --reason "Flow upgrade"',
      );
      await expect(maintenanceCommands).toContainText(
        "langflow maintenance status",
      );
      await maintenanceCommands.scrollIntoViewIfNeeded();
      await page.screenshot({
        path: test.info().outputPath("upgrade-report-maintenance-guidance.png"),
        fullPage: true,
      });
      await page
        .getByText("How to enable maintenance", { exact: true })
        .click();
      await page
        .getByRole("checkbox", { name: `Select ${flow.name} for preview` })
        .check();
      await page
        .getByRole("button", { name: "Preview selected updates" })
        .click();
      const apply = page.getByRole("button", {
        name: "Apply 1 reviewed update",
      });
      await expect(apply).toBeDisabled({ timeout: TIMEOUTS.standard });
      await expect(
        page.getByText(/Preview complete. No flows have changed/),
      ).toBeVisible();
      const unchanged = await page.request.get(`/api/v1/flows/${flow.id}`, {
        headers,
      });
      expect((await unchanged.json()).data).toEqual(graph);
      const paused = await page.request.post("/api/v1/maintenance/on", {
        headers,
        data: { reason: "Disposable upgrade workflow test" },
      });
      expect(paused.ok()).toBeTruthy();
      await page
        .getByRole("checkbox", { name: /I reviewed this 1 update/ })
        .check();
      await expect(apply).toBeEnabled({ timeout: TIMEOUTS.standard });
      await page.runA11yScan("upgrade-reports-real-preview");
      const appliedResponse = page.waitForResponse(
        "**/api/v1/upgrade-repairs/apply",
      );
      await apply.click();
      const applied = (await (await appliedResponse).json()) as RepairPreview;
      expect(applied.results).toHaveLength(1);
      expect(applied.results[0].status).toBe("updated");
      const recoveryId = applied.results[0].recovery_version_id;
      expect(recoveryId).toBeTruthy();
      await expect(
        page.getByRole("list", { name: "Update results" }).getByRole("link", {
          name: `Review protected recovery version for ${flow.name}`,
          exact: true,
        }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      const updated = await page.request.get(`/api/v1/flows/${flow.id}`, {
        headers,
      });
      const updatedFlow = await updated.json();
      const updatedGraph = updatedFlow.data;
      expect(updatedGraph.nodes[0].data.node.template.input_value.value).toBe(
        "Keep this saved input",
      );
      expect(updatedGraph.nodes[0].data.node.template.code.value).toBe(
        current.template.code.value,
      );
      expect(updatedGraph.edges).toEqual(graph.edges);
      await page.runA11yScan("upgrade-reports-real-updated");
      await page.screenshot({
        path: test.info().outputPath("upgrade-report-real-updated.png"),
        fullPage: true,
      });
      await page.reload();
      await page.getByText("Saved update outcomes", { exact: true }).click();
      await expect(
        page.getByText(/Showing 1 of 1 saved outcomes/),
      ).toBeVisible();
      const history = page.getByRole("group", {
        name: "Saved update outcomes",
      });
      await expect(
        history.getByRole("link", { name: `Open ${flow.name}`, exact: true }),
      ).toHaveAttribute("href", `/flow/${flow.id}`);
      const recoveryLink = history.getByRole("link", {
        name: `Review protected recovery version for ${flow.name}`,
        exact: true,
      });
      await expect(recoveryLink).toHaveAttribute(
        "href",
        `/flow/${flow.id}?version=${recoveryId}`,
      );
      expect(
        (await page.request.post("/api/v1/maintenance/off", { headers })).ok(),
      ).toBeTruthy();
      await expect(page.getByTestId("changes-paused-notice")).toBeEmpty({
        timeout: 45_000,
      });
      const maintenanceProbe = await page.request.get(
        "/api/v1/maintenance/status",
        { headers },
      );
      expect(maintenanceProbe.ok()).toBeTruthy();
      expect(await maintenanceProbe.json()).toMatchObject({
        maintenance: false,
        migration: false,
        running_jobs: 0,
      });
      await expect(
        page.getByText(
          "Maintenance status could not be verified. Updates are disabled.",
          { exact: true },
        ),
      ).toHaveCount(0);
      await recoveryLink.scrollIntoViewIfNeeded();
      await page.screenshot({
        path: test.info().outputPath("upgrade-report-saved-history.png"),
        fullPage: true,
      });

      const activations: string[] = [];
      page.on("request", (request) => {
        if (
          request.method() === "POST" &&
          request.url().includes(`/versions/${recoveryId}/activate`)
        )
          activations.push(request.url());
      });
      const recoveryPreview = page.waitForResponse(
        (response) =>
          response.request().method() === "GET" &&
          response.url().endsWith(`/flows/${flow.id}/versions/${recoveryId}`),
      );
      await recoveryLink.click();
      const recovery = await (await recoveryPreview).json();
      expect(recovery.data).toEqual(graph);
      expect(recovery.retained).toBe(true);
      expect(recovery.retained_reason).toBe("admin-upgrade-repair");
      await expect(
        page.getByText("Version History", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("(Read-Only)", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText(`Previewing ${recovery.version_tag}`, { exact: true }),
      ).toBeVisible();
      await expect(page.getByTestId("div-generic-node")).toHaveCount(1);
      expect(activations).toHaveLength(0);
      const stillRepaired = await page.request.get(`/api/v1/flows/${flow.id}`, {
        headers,
      });
      const unchangedAfterPreview = await stillRepaired.json();
      expect(unchangedAfterPreview.data).toEqual(updatedGraph);
      expect(unchangedAfterPreview.version_token).toBe(
        updatedFlow.version_token,
      );
      await page.screenshot({
        path: test.info().outputPath("upgrade-report-recovery-preview.png"),
        fullPage: true,
      });

      await page.getByRole("button", { name: "Restore", exact: true }).click();
      await expect(
        page.getByLabel("Save current draft before restoring"),
      ).toBeChecked();
      const restoredResponse = page.waitForResponse(
        `**/api/v1/flows/${flow.id}/versions/${recoveryId}/activate*`,
      );
      await page
        .getByRole("button", { name: "Restore", exact: true })
        .last()
        .click();
      const restored = await restoredResponse;
      expect(restored.ok()).toBeTruthy();
      expect(restored.request().headers()["if-match"]).toBe(
        updatedFlow.version_token,
      );
      const restoredFlow = await restored.json();
      expect(restoredFlow.data).toEqual(graph);
      expect(restoredFlow.version_token).not.toBe(updatedFlow.version_token);
      expect(activations).toHaveLength(1);
      const persistedRestore = await page.request.get(
        `/api/v1/flows/${flow.id}`,
        {
          headers,
        },
      );
      expect((await persistedRestore.json()).data).toEqual(graph);
    } finally {
      expect(
        (await page.request.post("/api/v1/maintenance/off", { headers })).ok(),
      ).toBeTruthy();
      expect(
        (
          await page.request.delete(`/api/v1/flows/${flow.id}`, { headers })
        ).ok(),
      ).toBeTruthy();
    }
  },
);
