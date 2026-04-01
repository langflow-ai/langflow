import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { getAuthToken } from "../../utils/auth-helpers";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "vector store from starter projects should have its connections and nodes on the flow",
  { tag: ["@release", "@starter-projects", "@mainpage"] },
  async ({ page, request }) => {
    // Get authentication token
    const authToken = await getAuthToken(request);

    const response = await request.get("/api/v1/starter-projects", {
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    });
    expect(response.status()).toBe(200);
    const responseBody = await response.json();

    const astraStarterProject = responseBody.find((project: any) => {
      if (project.data.nodes) {
        return project.data.nodes.some((node: any) =>
          node.id.includes("Astra"),
        );
      }
    });

    await page.route("**/api/v1/flows/", async (route) => {
      if (route.request().method() === "GET") {
        try {
          // Add authorization header to the request
          const headers = route.request().headers();
          headers["Authorization"] = `Bearer ${authToken}`;

          const response = await route.fetch({
            headers: headers,
          });
          const flowsData = await response.json();

          const modifiedFlows = flowsData.map((flow: any) => {
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

    await adjustScreenView(page);

    const edges = await page.locator(".react-flow__edge-interaction").count();
    const nodes = await page.getByTestId("div-generic-node").count();

    const edgesFromServer = astraStarterProject?.data.edges.length;
    const nodesFromServer = astraStarterProject?.data.nodes.length;

    expect(
      edges === edgesFromServer ||
        edges === edgesFromServer - 1 ||
        edges === edgesFromServer - 2,
    ).toBeTruthy();
    expect(nodes).toBe(nodesFromServer);
  },
);
