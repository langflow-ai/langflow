import type { Page } from "@playwright/test";
import fs from "fs";
import path from "path";
import { expect } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { buildFlowAndWait } from "../../utils/flow/build-flow-and-wait";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { sendPlaygroundMessage } from "../../utils/playground/send-playground-message";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

type KnowledgeBaseListItem = {
  dir_name?: string;
  name?: string;
  status?: string;
  chunks?: number;
  failure_reason?: string | null;
};

async function waitForKnowledgeBaseReady(page: Page, kbName: string) {
  const deadline = Date.now() + 120000;
  let lastStatus = "missing";

  while (Date.now() < deadline) {
    const listResponse = await page.request.get("/api/v1/knowledge_bases");
    expect(listResponse.ok()).toBeTruthy();

    const knowledgeBases =
      (await listResponse.json()) as KnowledgeBaseListItem[];
    const knowledgeBase = knowledgeBases.find(
      (item) => item.dir_name === kbName || item.name === kbName,
    );

    if (knowledgeBase) {
      lastStatus = knowledgeBase.status ?? "unknown";
      if (lastStatus === "ready" && Number(knowledgeBase.chunks ?? 0) > 0) {
        return;
      }
      if (lastStatus === "failed") {
        throw new Error(
          `Knowledge Base ingestion failed for ${kbName}: ${
            knowledgeBase.failure_reason ?? "no failure reason"
          }`,
        );
      }
    }

    await page.waitForTimeout(2000);
  }

  throw new Error(
    `Timed out waiting for Knowledge Base ${kbName} to be ready; last status was ${lastStatus}`,
  );
}

async function seedKnowledgeBase(page: Page, kbName: string) {
  await awaitBootstrapTest(page, { skipModal: true });

  const createResponse = await page.request.post("/api/v1/knowledge_bases", {
    data: {
      name: kbName,
      embedding_provider: "OpenAI",
      embedding_model: "text-embedding-3-small",
      model_selection: {
        name: "text-embedding-3-small",
        provider: "OpenAI",
      },
      column_config: [
        {
          column_name: "text",
          vectorize: true,
          identifier: true,
        },
      ],
      backend_type: "chroma",
      backend_config: {},
    },
  });
  expect(createResponse.status()).toBe(201);

  const fileName = "test_file.txt";
  const ingestResponse = await page.request.post(
    `/api/v1/knowledge_bases/${kbName}/ingest`,
    {
      multipart: {
        files: {
          name: fileName,
          mimeType: "text/plain",
          buffer: fs.readFileSync(
            path.join(__dirname, "../../assets", fileName),
          ),
        },
        source_name: "Document QA test",
        chunk_size: "1000",
        chunk_overlap: "200",
        separator: "\n",
      },
      timeout: 120000,
    },
  );
  expect(ingestResponse.ok()).toBeTruthy();
  await waitForKnowledgeBaseReady(page, kbName);
}

async function selectKnowledgeBase(page: Page, kbName: string) {
  await page.getByTestId("rf__node-KnowledgeRetrieve-docqa").click();
  const knowledgeDropdown = page.getByTestId("dropdown_str_knowledge_base");

  await knowledgeDropdown.click();
  if ((await page.getByText(kbName, { exact: true }).count()) === 0) {
    await page.getByTestId("refresh-dropdown-list-knowledge_base").click();
    await expect(knowledgeDropdown).toBeVisible({ timeout: 30000 });
    await knowledgeDropdown.click();
  }

  await page.getByTestId("dropdown_search_input").fill(kbName);
  await page.getByTestId("dropdown-option-0-container").click();
  await expect(
    page.getByTestId("value-dropdown-dropdown_str_knowledge_base"),
  ).toContainText(kbName);
}

withEventDeliveryModes(
  "Document Q&A",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);

    const kbName = `document_qa_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    try {
      await seedKnowledgeBase(page, kbName);
      await openStarterProject(page, "Document Q&A");
      await initialGPTsetup(page);
      await selectKnowledgeBase(page, kbName);

      await page.waitForSelector('[data-testid="button_run_chat output"]', {
        timeout: 3000,
      });
      await buildFlowAndWait(page);

      await page
        .getByRole("button", { name: TEXTS.playground, exact: true })
        .click();
      await page
        .getByText(TEXTS.labelNoInputMessage, { exact: true })
        .last()
        .isVisible();

      // Create a new session first
      await page.getByTestId("new-chat").click();

      await sendPlaygroundMessage(page, "whats the text in the file?");

      await page.waitForSelector("text=this is a test file", {
        timeout: 10000,
      });

      await expect(page.getByText("this is a test file").last()).toBeVisible();
      expect(await page.getByTestId("div-chat-message").last().count()).toBe(1);
    } finally {
      await page.request
        .delete(`/api/v1/knowledge_bases/${kbName}`)
        .catch(() => undefined);
    }
  },
);
