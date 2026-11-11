import { readFile } from "node:fs/promises";
import path from "node:path";
import type { ReportDetail } from "../../src/controllers/API/queries/upgrade-reports";
import type { APIClassType } from "../../src/types/api";
import { expect, test } from "../fixtures";
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
      await apply.click();
      await expect(
        page
          .getByRole("list", { name: "Update results" })
          .getByText(/Protected recovery version/),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      const updated = await page.request.get(`/api/v1/flows/${flow.id}`, {
        headers,
      });
      const updatedGraph = (await updated.json()).data;
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
