import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TID } from "../../utils/constants/testIds";
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

/** A public Chat Input -> Chat Output flow: it echoes without a model. */
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
      name: `shared-new-chat-${Date.now()}`,
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

async function ask(page: Page, question: string) {
  await page.getByPlaceholder(TEXTS.placeholderSendMessage).fill(question);
  await page.getByTestId(TID.buttonSend).last().click();
}

test(
  "shareable playground: a new chat shows the reply to its first question",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });
    const flowId = await createPublicEchoFlow(page);

    try {
      await page.goto(`/playground/${flowId}`);
      await page
        .getByPlaceholder(TEXTS.placeholderSendMessage)
        .waitFor({ state: "visible", timeout: TIMEOUTS.long });

      const replies = page.getByTestId(TID.chatMessage);
      await ask(page, "first question");
      await expect(replies).toHaveText(["first question"], {
        timeout: TIMEOUTS.standard,
      });

      await page.getByTestId(TID.newChat).click();
      await ask(page, "second question");

      await expect(page.getByTestId(TID.sessionSelector)).toHaveCount(2, {
        timeout: TIMEOUTS.standard,
      });
      await expect(replies).toHaveText(["second question"], {
        timeout: TIMEOUTS.standard,
      });

      await page.reload();
      await page.getByTestId(TID.sessionSelector).last().click();
      await expect(replies).toHaveText(["second question"], {
        timeout: TIMEOUTS.standard,
      });
    } finally {
      await page.request.delete(`/api/v1/flows/${flowId}`);
    }
  },
);
