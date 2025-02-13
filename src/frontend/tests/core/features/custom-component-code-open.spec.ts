import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "custom component code should be opened after adding a custom component",
  { tag: ["@release", "@components"] },

  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 3000,
    });

    await page.getByTestId("blank-flow").click();
    await page.getByTestId('sidebar-custom-component-button').click();
    await expect(page.getByText('Edit Code')).toBeVisible({timeout: 3000});
},
);
