import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import type {
  RepairOutcome,
  RepairPreview,
  ReportDocument,
} from "../../../src/controllers/API/queries/upgrade-reports";
import type { APIClassType, APIObjectType } from "../../../src/types/api";
import type { FlowType } from "../../../src/types/flow";
import type {
  FlowVersionEntry,
  FlowVersionEntryWithData,
} from "../../../src/types/flow/version";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// This test freezes writes for the entire instance. Run only against a dedicated,
// disposable database, with no other tests sharing the server.
test.skip(
  process.env.LANGFLOW_TEST_ADMIN_REPAIRS !== "1",
  "Requires an isolated disposable instance for the maintenance window",
);

test(
  "repairs only the reviewed flow and restores its retained recovery version",
  { tag: ["@release", "@database", "@workspace", "@api"] },
  async ({ page }, testInfo) => {
    await awaitBootstrapTest(page, {
      skipModal: true,
      seedFlowIfEmpty: false,
    });
    const initialMaintenance = await page.request.get(
      "/api/v1/maintenance/status",
    );
    expect(initialMaintenance.ok()).toBeTruthy();
    expect((await initialMaintenance.json()).maintenance).toBe(false);

    const catalogResponse = await page.request.get("/api/v1/all");
    expect(catalogResponse.ok()).toBeTruthy();
    const catalog = (await catalogResponse.json()) as APIObjectType;
    const definitions = Object.assign({}, ...Object.values(catalog)) as Record<
      string,
      APIClassType
    >;
    const target = definitions.ChatOutput;
    expect(target).toBeTruthy();
    const historical = structuredClone(target);
    historical.edited = false;
    historical.template.code.value +=
      "\n# Historical administrator repair fixture\n";
    historical.template.input_value.value = "Saved owner text";
    historical.template.input_value.show = false;
    const nodeId = `ChatOutput-${randomUUID()}`;
    const name = `Selected repair ${randomUUID()}`;
    const data = {
      nodes: [
        {
          id: nodeId,
          type: "genericNode",
          position: { x: 0, y: 0 },
          data: { id: nodeId, type: "ChatOutput", node: historical },
        },
      ],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    const create = async (flowName: string) => {
      const response = await page.request.post("/api/v1/flows/", {
        data: { name: flowName, data },
      });
      expect(response.status()).toBe(201);
      return (await response.json()) as FlowType;
    };
    const selected = await create(name);
    const unselected = await create(`Unselected repair ${randomUUID()}`);
    const readFlow = async (id: string) => {
      const response = await page.request.get(`/api/v1/flows/${id}`);
      expect(response.ok()).toBeTruthy();
      return (await response.json()) as FlowType;
    };
    const before = await readFlow(selected.id);
    const otherBefore = await readFlow(unselected.id);
    const report = JSON.parse(
      await readFile(
        path.resolve(
          __dirname,
          "../../../../backend/tests/unit/api/v1/fixtures/upgrade-report-v1.json",
        ),
        "utf8",
      ),
    ) as ReportDocument;
    report.generated_at = new Date().toISOString();
    report.target.langflow = "historical fixture";
    report.summary.flows = { ok: 0, warn: 1, fail: 0 };
    report.summary.nodes = { outdated_safe: 1 };
    report.flows = [
      {
        ...report.flows[0],
        id: selected.id,
        name,
        owner: { id: selected.user_id ?? null, username: "langflow" },
        nodes: [
          {
            ...report.flows[0].nodes[0],
            id: nodeId,
            type: "ChatOutput",
            display_name: "Chat Output",
            status: "outdated_safe",
            reasons: [],
            dry_run: { result: "safe" },
          },
        ],
      },
    ];
    await page.goto("/settings/upgrade-reports");
    await expect(
      page.getByRole("heading", { name: "Upgrade reports", exact: true }),
    ).toBeVisible();
    await page.getByLabel("Checker report file").setInputFiles({
      name: "selected-repair.json",
      mimeType: "application/json",
      buffer: Buffer.from(`${JSON.stringify(report)}\n`),
    });
    await page
      .getByRole("button", { name: "Import report", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
    const reportId = new URL(page.url()).searchParams.get("report");
    expect(reportId).toBeTruthy();
    await page
      .getByRole("checkbox", { name: `Select ${name} for preview` })
      .check();
    const previewResponse = page.waitForResponse(
      "**/api/v1/upgrade-repairs/preview",
    );
    await page
      .getByRole("button", { name: "Preview selected updates" })
      .click();
    const preview = (await (await previewResponse).json()) as RepairPreview;
    expect(preview.results).toHaveLength(1);
    expect(preview.results[0]).toMatchObject({
      flow_id: selected.id,
      status: "ready",
      version_token: before.version_token,
      updated_nodes: 1,
    });
    expect(preview.target_version).not.toBe(report.target.langflow);
    const apply = page.getByRole("button", { name: "Apply 1 reviewed update" });
    await page
      .getByRole("checkbox", { name: /I reviewed this 1 update/ })
      .check();
    await expect(apply).toBeDisabled();
    await page.runA11yScan("admin-repairs-real-preview");

    let maintenanceEnabled = false;
    try {
      const freeze = await page.request.post("/api/v1/maintenance/on", {
        data: { reason: "Isolated browser repair verification" },
      });
      expect(freeze.ok()).toBeTruthy();
      maintenanceEnabled = true;
      await expect(apply).toBeEnabled({ timeout: 15_000 });
      const applyResponse = page.waitForResponse(
        "**/api/v1/upgrade-repairs/apply",
      );
      await apply.click();
      const applied = (await (await applyResponse).json()) as RepairPreview;
      expect(applied.results).toHaveLength(1);
      const [outcome] = applied.results;
      expect(outcome.status).toBe("updated");
      expect(outcome.recovery_version_id).toBeTruthy();
      const recoveryId = outcome.recovery_version_id!;
      await expect(
        page.getByRole("list", { name: "Update results" }).getByRole("link", {
          name: `Review protected recovery version for ${name}`,
        }),
      ).toHaveAttribute("href", `/flow/${selected.id}?version=${recoveryId}`);
      await page.getByText("Saved update outcomes", { exact: true }).click();
      await expect(
        page.getByText("Showing 1 of 1 saved outcomes"),
      ).toBeVisible();
      await page.runA11yScan("admin-repairs-real-outcome");
      const repaired = await readFlow(selected.id);
      expect(repaired.user_id).toBe(before.user_id);
      expect(repaired.version_token).not.toBe(before.version_token);
      expect(repaired.data?.nodes[0].data.node?.template.code.value).toBe(
        target.template.code.value,
      );
      expect(
        repaired.data?.nodes[0].data.node?.template.input_value.value,
      ).toBe("Saved owner text");
      expect(await readFlow(unselected.id)).toEqual(otherBefore);
      const recoveryResponse = await page.request.get(
        `/api/v1/flows/${selected.id}/versions/${recoveryId}`,
      );
      expect(recoveryResponse.ok()).toBeTruthy();
      const recovery =
        (await recoveryResponse.json()) as FlowVersionEntryWithData & {
          retained: boolean;
          retained_reason: string;
        };
      expect(recovery.data).toEqual(before.data);
      expect(recovery.user_id).toBe(before.user_id);
      expect(recovery.retained).toBe(true);
      expect(recovery.retained_reason).toBe("admin-upgrade-repair");
      await page.reload();
      await page.getByText("Saved update outcomes", { exact: true }).click();
      await expect(
        page.getByText("Showing 1 of 1 saved outcomes"),
      ).toBeVisible();
      const savedResponse = await page.request.get(
        `/api/v1/upgrade-reports/${reportId}/repairs`,
      );
      expect(savedResponse.ok()).toBeTruthy();
      const saved = (await savedResponse.json()) as { items: RepairOutcome[] };
      expect(saved.items[0].result).toEqual(outcome);
      await testInfo.attach("persisted-repair-proof", {
        body: JSON.stringify({ preview, applied, recovery, saved }, null, 2),
        contentType: "application/json",
      });

      const thaw = await page.request.post("/api/v1/maintenance/off");
      expect(thaw.ok()).toBeTruthy();
      maintenanceEnabled = false;
      await page.goto(`/flow/${selected.id}`);
      await expect(page.getByTestId("div-generic-node")).toHaveCount(1);
      await page.getByTestId("sidebar-nav-versions").click();
      await page
        .getByRole("button", { name: new RegExp(recovery.version_tag) })
        .click();
      await page.getByRole("button", { name: "Restore", exact: true }).click();
      const activationResponse = page.waitForResponse(
        `**/api/v1/flows/${selected.id}/versions/${recoveryId}/activate*`,
      );
      await page
        .getByRole("button", { name: "Restore", exact: true })
        .last()
        .click();
      const activated = await activationResponse;
      expect(activated.status()).toBe(200);
      expect(activated.request().headers()["if-match"]).toBe(
        repaired.version_token,
      );
      const restored = (await activated.json()) as FlowType;
      expect(restored.data).toEqual(before.data);
      expect(restored.version_token).not.toBe(repaired.version_token);
      const versions = await page.request.get(
        `/api/v1/flows/${selected.id}/versions/`,
      );
      expect(versions.ok()).toBeTruthy();
      expect(
        (
          (await versions.json()) as { entries: FlowVersionEntry[] }
        ).entries.some((entry) => entry.id === recoveryId),
      ).toBe(true);
    } finally {
      if (maintenanceEnabled) {
        const thaw = await page.request.post("/api/v1/maintenance/off");
        expect(thaw.ok()).toBeTruthy();
      }
    }
  },
);
