import { expect } from "../../fixtures";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Blog Writer",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    await openStarterProject(page, "Blog Writer");

    await expect(page.getByTestId("title-URL")).toBeVisible();
    await expect(page.getByTestId("title-Agent")).toBeVisible();
    await expect(page.getByTestId("title-Chat Input")).toBeVisible();
    await expect(page.getByTestId("title-Chat Output")).toBeVisible();
  },
);
