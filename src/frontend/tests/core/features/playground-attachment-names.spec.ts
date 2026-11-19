import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { TIMEOUTS } from "../../utils/constants/timeouts";

type ComponentTemplate = {
  template: { input_value: { input_types: string[] } };
};

const encodeHandle = (handle: Record<string, unknown>) =>
  JSON.stringify(
    Object.fromEntries(
      Object.entries(handle).sort(([a], [b]) => a.localeCompare(b)),
    ),
  ).replace(/"/g, "œ");

/** A Chat Input -> Chat Output flow: it runs without a model. */
async function createEchoFlow(page: Page): Promise<string> {
  const all = (await (await page.request.get("/api/v1/all")).json()) as Record<
    string,
    Record<string, ComponentTemplate>
  >;
  const find = (name: string) =>
    Object.values(all).find((category) => name in category)?.[name];
  const chatInput = find("ChatInput");
  const chatOutput = find("ChatOutput");
  expect(chatInput && chatOutput).toBeTruthy();

  const sourceHandle = {
    dataType: "ChatInput",
    id: "ChatInput-files1",
    name: "message",
    output_types: ["Message"],
  };
  const targetHandle = {
    fieldName: "input_value",
    id: "ChatOutput-files2",
    inputTypes: chatOutput!.template.input_value.input_types,
    type: "other",
  };
  const created = await page.request.post("/api/v1/flows/", {
    data: {
      name: `attachment-names-${Date.now()}`,
      data: {
        nodes: [
          {
            id: "ChatInput-files1",
            type: "genericNode",
            position: { x: 0, y: 0 },
            data: {
              id: "ChatInput-files1",
              type: "ChatInput",
              node: chatInput,
            },
          },
          {
            id: "ChatOutput-files2",
            type: "genericNode",
            position: { x: 400, y: 0 },
            data: {
              id: "ChatOutput-files2",
              type: "ChatOutput",
              node: chatOutput,
            },
          },
        ],
        edges: [
          {
            id: "files-edge",
            source: "ChatInput-files1",
            target: "ChatOutput-files2",
            sourceHandle: encodeHandle(sourceHandle),
            targetHandle: encodeHandle(targetHandle),
            data: { sourceHandle, targetHandle },
          },
        ],
        viewport: { x: 0, y: 0, zoom: 1 },
      },
    },
  });
  expect(created.status()).toBe(201);
  return (await created.json()).id;
}

const textFile = (name: string) => ({
  name,
  mimeType: "text/plain",
  buffer: Buffer.from(`contents of ${name}`),
});

test(
  "playground attachments show their names in the input and the sent message",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });
    const flowId = await createEchoFlow(page);

    try {
      await page.goto(`/flow/${flowId}`);
      await page
        .getByRole("button", { name: TEXTS.playground, exact: true })
        .click();
      await page
        .getByTestId("input-chat-playground")
        .waitFor({ timeout: TIMEOUTS.long });

      const fileInput = page.locator('input[type="file"]');
      for (const name of ["notes.txt", "customer_list_export.txt"]) {
        const uploaded = page.waitForResponse(
          (response) =>
            response.request().method() === "POST" &&
            response.url().includes("/files/upload/") &&
            response.ok(),
        );
        await fileInput.setInputFiles(textFile(name));
        await uploaded;
      }

      await expect(page.getByText("notes.txt", { exact: true })).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      const truncated = page.getByText("custom...txt", { exact: true });
      await expect(truncated).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Delete customer_list_export.txt" }),
      ).toBeVisible();
      await page.runA11yScan("playground-attachments-in-input");
      await truncated.hover();
      await expect(page.getByRole("tooltip")).toHaveText(
        "customer_list_export.txt",
      );

      await page.getByTestId("input-chat-playground").fill("see attached");
      await page.getByTestId("button-send").click();

      // The server stores each file under a timestamp prefix; the message
      // still names it as uploaded.
      await expect(page.getByText("notes.txt", { exact: true })).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(
        page.getByText("customer_l...txt", { exact: true }),
      ).toBeVisible();
      // The echo means the run finished; the canvas build toast behind the
      // playground then fades out, and the scan must not catch it midway.
      await expect(page.getByText("see attached", { exact: true })).toHaveCount(
        2,
        { timeout: TIMEOUTS.standard },
      );
      await expect(page.getByTestId("stop_building_button")).toBeHidden({
        timeout: TIMEOUTS.standard,
      });
      await page.runA11yScan("playground-attachments-in-message");
    } finally {
      await page.request.delete(`/api/v1/flows/${flowId}`);
    }
  },
);
