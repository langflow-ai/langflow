import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { getAuthToken } from "../../utils/auth-helpers";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "vector store from starter projects should have its connections and nodes on the flow",
  { tag: ["@release", "@starter-projects", "@mainpage"] },
  async ({ page, request }) => {
    const authToken = await getAuthToken(request);

    const response = await request.get("/api/v1/starter-projects", {
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    });
    expect(response.status()).toBe(200);
    const responseBody = await response.json();

    // Find the Vector Store RAG starter project — it now uses native
    // KnowledgeIngestion / KnowledgeBase components instead of AstraDB.
    const vectorStoreProject = responseBody.find((project: any) => {
      return project.name === "Vector Store RAG";
    });

    expect(vectorStoreProject).toBeDefined();

    // Verify the template uses the native Knowledge components
    const nodeTypes: string[] = (vectorStoreProject?.data?.nodes ?? []).map(
      (node: any) => node.data?.type as string,
    );

    expect(nodeTypes).toContain("KnowledgeIngestion");
    expect(nodeTypes).toContain("KnowledgeBase");
    expect(nodeTypes).not.toContain("AstraDBVectorStore");

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Vector Store RAG" })
      .first()
      .click();
    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await adjustScreenView(page);

    const edges = await page.locator(".react-flow__edge-interaction").count();
    const nodes = await page.getByTestId("div-generic-node").count();

    const edgesFromServer: number =
      vectorStoreProject?.data?.edges?.length ?? 0;
    const nodesFromServer: number =
      vectorStoreProject?.data?.nodes?.length ?? 0;

    // Allow ±2 edge variance to account for animated/virtual edges
    expect(
      edges === edgesFromServer ||
        edges === edgesFromServer - 1 ||
        edges === edgesFromServer - 2,
    ).toBeTruthy();
    expect(nodes).toBe(nodesFromServer);
  },
);
