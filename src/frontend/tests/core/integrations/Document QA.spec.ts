import { expect } from "../../fixtures";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Document Q&A",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    await page.route(/\/api\/v1\/store\/tags(\?.*)?$/, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ json: [] });
        return;
      }

      await route.continue();
    });
    await openStarterProject(page, "Document Q&A");

    await expect(page.getByTestId("title-Knowledge")).toBeVisible();
    await expect(page.getByTestId("title-Agent")).toBeVisible();
    await expect(page.getByTestId("title-Chat Input")).toBeVisible();
    await expect(page.getByTestId("title-Chat Output")).toBeVisible();
    await expect(page.getByTestId("dropdown_str_knowledge_base")).toBeVisible();
  },
);
