import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// Helper function to get JWT token for API requests
async function getAuthToken(request: any) {
  const formData = new URLSearchParams();
  formData.append("username", "langflow");
  formData.append("password", "langflow");

  const loginResponse = await request.post("/api/v1/login", {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    data: formData.toString(),
  });

  expect(loginResponse.status()).toBe(200);
  const tokenData = await loginResponse.json();
  return tokenData.access_token;
}

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

    const astraStarterProject = responseBody.find((project) => {
      if (project.data.nodes) {
        return project.data.nodes.some((node) => node.id.includes("Astra"));
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

    await page.getByTestId("canvas_controls_dropdown").click();
    await page.getByTestId("fit_view").click();
    await page.getByTestId("canvas_controls_dropdown").click();

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

test(
  "user should be able to use all starter projects without any outdated components on the flow",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();

    const numberOfTemplates = await page
      .getByTestId("text_card_container")
      .count();

    let numberOfOutdatedComponents = 0;

    for (let i = 0; i < numberOfTemplates; i++) {
      const exampleName = await page
        .getByTestId("text_card_container")
        .nth(i)
        .getAttribute("role");

      await page.getByTestId("text_card_container").nth(i).click();

      await page.waitForSelector('[data-testid="div-generic-node"]', {
        timeout: 5000,
      });

      if ((await page.getByTestId("update-all-button").count()) > 0) {
        console.error(`
          ---------------------------------------------------------------------------------------
          There's an outdated component on the basic template: ${exampleName}
          ---------------------------------------------------------------------------------------
          `);
        numberOfOutdatedComponents++;
      }

      await Promise.all([
        page.waitForURL((url) => url.pathname === "/", { timeout: 30000 }),
        page.getByTestId("icon-ChevronLeft").click(),
      ]);

      await expect(page.getByTestId("mainpage_title")).toBeVisible({
        timeout: 30000,
      });

      await page.waitForTimeout(500);

      await page.waitForSelector('[data-testid="new-project-btn"]', {
        timeout: 5000,
      });

      await page.getByTestId("new-project-btn").first().click();

      await page.waitForSelector(
        '[data-testid="side_nav_options_all-templates"]',
        {
          timeout: 5000,
        },
      );

      await page.getByTestId("side_nav_options_all-templates").click();
    }

    expect(numberOfOutdatedComponents).toBe(0);
  },
);
