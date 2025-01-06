import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "vector store from starter projects should have its connections and nodes on the flow",
  { tag: ["@release", "@starter-project"] },
  async ({ page, request }) => {
    const response = await request.get("/api/v1/starter-projects");
    expect(response.status()).toBe(200);
    const responseBody = await response.json();

    const astraStarterProject = responseBody.find((project) => {
      if (project.data.nodes) {
        return project.data.nodes.some((node) => node.id.includes("Astra"));
      }
    });

    await page.route("**/api/v1/flows/", async (route) => {
      if (route.request().method() === "GET") {
        try {
          const response = await route.fetch();
          const flowsData = await response.json();

          const modifiedFlows = flowsData.map((flow) => {
            if (flow.name === "Vector Store RAG" && flow.user_id === null) {
              return {
                ...flow,
                data: astraStarterProject?.data,
              };
            }
            return flow;
          });

          const modifiedResponse = JSON.stringify(modifiedFlows);

          route.fulfill({
            status: response.status(),
            headers: response.headers(),
            body: modifiedResponse,
          });
        } catch (error) {
          console.error("Error in route handler:", error);
        }
      } else {
        // If not a GET request, continue without modifying
        await route.continue();
      }
    });

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Vector Store RAG" })
      .first()
      .click();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();

    const edges = await page.locator(".react-flow__edge-interaction").count();
    const nodes = await page.getByTestId("div-generic-node").count();

    const edgesFromServer = astraStarterProject?.data.edges.length;
    const nodesFromServer = astraStarterProject?.data.nodes.length;

    expect(edges).toBe(edgesFromServer);
    expect(nodes).toBe(nodesFromServer);
  },
);
