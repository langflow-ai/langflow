import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { uploadFile } from "../../utils/upload-file";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

// biome-ignore lint/suspicious/noExplicitAny: process not in tsconfig scope for test files
declare const process: any;

withEventDeliveryModes(
  "Vector Store RAG",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Vector Store RAG" })
      .first()
      .click();
    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    // Confirm the template uses native Knowledge components (no AstraDB)
    await expect(page.getByTestId("title-Knowledge Ingestion")).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByTestId("title-Knowledge Base")).toBeVisible();
    await expect(page.getByTestId("title-Astra DB")).toHaveCount(0);

    // Upload a test file to the File component
    await uploadFile(page, "test_file.txt");

    // --- Load Data flow: create a knowledge base and ingest the file ---

    // Scope to the KnowledgeIngestion node to avoid ambiguity with the
    // KnowledgeBase node, which shares the same dropdown testid.
    const knowledgeIngestionNode = page.locator(".react-flow__node", {
      has: page.getByTestId("title-Knowledge Ingestion"),
    });

    await knowledgeIngestionNode
      .getByTestId("dropdown_str_knowledge_base")
      .click();

    // Click "Create new knowledge" to open the creation dialog
    await page.getByText("Create new knowledge").click();

    // Fill in the knowledge base name
    await page
      .getByTestId("popover-anchor-input-01_new_kb_name")
      .fill("test-kb-rag");

    // Choose the first available embedding model (requires OpenAI key set via
    // initialGPTsetup → selectGptModel → manage-model-providers)
    await page.getByTestId("model_embedding_model").click();
    await page.waitForSelector('[role="listbox"]', { timeout: 10000 });
    await page.getByRole("listbox").getByRole("option").first().click();

    // Submit the dialog — button text comes from functionality: "create"
    await page.getByRole("button", { name: "create", exact: true }).click();

    await page.waitForSelector("text=created successfully", { timeout: 30000 });

    // Run KnowledgeIngestion to ingest the uploaded file into the new KB
    await page.getByTestId("button_run_knowledge ingestion").click();
    await page.waitForSelector("text=built successfully", {
      timeout: 120000,
    });

    // --- Retriever flow: select the KB and run the RAG pipeline ---

    const knowledgeBaseNode = page.locator(".react-flow__node", {
      has: page.getByTestId("title-Knowledge Base"),
    });

    // Refresh the KB list so the newly ingested KB appears
    await knowledgeBaseNode.getByTestId("dropdown_str_knowledge_base").click();
    await page.getByTestId("refresh-dropdown-list-knowledge_base").click();
    await page.waitForTimeout(1000);
    await knowledgeBaseNode.getByTestId("dropdown_str_knowledge_base").click();
    await page.getByTestId("test-kb-rag-0-option").click();

    // Run the full RAG pipeline
    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", {
      timeout: 120000,
    });

    // --- Playground: verify context-aware retrieval ---

    await page.getByRole("button", { name: "Playground", exact: true }).click();
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 60000,
    });

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("what is the text in the file?");
    await page.keyboard.press("Enter");

    // The test file contains "this is a test file" — verify retrieval works
    await page.waitForSelector("text=this is a test file", {
      timeout: 120000,
    });
    await expect(page.getByText("this is a test file").last()).toBeVisible();
  },
  { timeout: 120000 },
);
