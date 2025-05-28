import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "vector store from starter projects should have its connections and nodes on the flow",
  { tag: ["@release", "@starter-projects"] },
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

    const edges = await page.locator(".react-flow__edge-interaction").count();
    const nodes = await page.getByTestId("div-generic-node").count();

    const edgesFromServer = astraStarterProject?.data.edges.length;
    const nodesFromServer = astraStarterProject?.data.nodes.length;

    expect(
      edges === edgesFromServer || edges === edgesFromServer - 1,
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

      await page.waitForSelector('[data-testid="fit_view"]', {
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

      await page.getByTestId("icon-ChevronLeft").click();
      await page.waitForSelector('[data-testid="mainpage_title"]', {
        timeout: 5000,
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
