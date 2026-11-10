import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TID } from "../../utils/constants/testIds";
import { TEXTS } from "../../utils/constants/texts";
import { TIMEOUTS } from "../../utils/constants/timeouts";

type ComponentTemplate = {
  template: { input_value: { input_types: string[] } };
};

const FLOW_NAME = "Quarterly planning assistant with attachments";

const encodeHandle = (handle: Record<string, unknown>) =>
  JSON.stringify(
    Object.fromEntries(
      Object.entries(handle).sort(([a], [b]) => a.localeCompare(b)),
    ),
  ).replace(/"/g, "œ");

/** A public Chat Input -> Chat Output flow with a long name: it echoes without a model. */
async function createPublicEchoFlow(page: Page): Promise<string> {
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
    id: "ChatInput-echo1",
    name: "message",
    output_types: ["Message"],
  };
  const targetHandle = {
    fieldName: "input_value",
    id: "ChatOutput-echo2",
    inputTypes: chatOutput!.template.input_value.input_types,
    type: "other",
  };
  const created = await page.request.post("/api/v1/flows/", {
    data: {
      name: `${FLOW_NAME} ${Date.now()}`,
      access_type: "PUBLIC",
      data: {
        nodes: [
          {
            id: "ChatInput-echo1",
            type: "genericNode",
            position: { x: 0, y: 0 },
            data: { id: "ChatInput-echo1", type: "ChatInput", node: chatInput },
          },
          {
            id: "ChatOutput-echo2",
            type: "genericNode",
            position: { x: 400, y: 0 },
            data: {
              id: "ChatOutput-echo2",
              type: "ChatOutput",
              node: chatOutput,
            },
          },
        ],
        edges: [
          {
            id: "echo-edge",
            source: "ChatInput-echo1",
            target: "ChatOutput-echo2",
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

test(
  "shareable playground: a message with an attachment is sent",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });
    const flowId = await createPublicEchoFlow(page);

    try {
      await page.goto(`/playground/${flowId}`);
      const input = page.getByPlaceholder(TEXTS.placeholderSendMessage);
      await input.waitFor({ state: "visible", timeout: TIMEOUTS.long });

      // A long flow name truncates instead of pushing the sidebar toggle off the panel.
      const toggle = page.getByRole("button", { name: "Hide sidebar" });
      await expect(toggle).toBeInViewport({ ratio: 1 });

      const uploaded = page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          response.url().includes("/files/upload/") &&
          response.ok(),
      );
      await page.locator('input[type="file"]').setInputFiles({
        name: "meeting-notes-final-v2.txt",
        mimeType: "text/plain",
        buffer: Buffer.from("meeting notes"),
      });
      await uploaded;

      const run = page.waitForResponse((response) =>
        response.url().includes("/api/v2/workflows/public"),
      );
      await input.fill("see attached");
      await page.getByTestId(TID.buttonSend).last().click();
      expect((await run).status()).toBe(200);

      await expect(page.getByTestId(TID.chatMessage)).toHaveText(
        ["see attached"],
        { timeout: TIMEOUTS.standard },
      );
      await expect(
        page.getByText("meeting-notes-final-v2.txt").first(),
      ).toBeVisible();
      await page.runA11yScan("shareable-playground-attachment-sent");
    } finally {
      await page.request.delete(`/api/v1/flows/${flowId}`);
    }
  },
);
