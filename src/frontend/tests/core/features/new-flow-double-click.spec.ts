import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TIMEOUTS } from "../../utils/constants/timeouts";

test(
  "a second New Flow click while creating opens the one flow it creates",
  { tag: ["@release", "@mainpage"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });
    const created: string[] = [];
    const creates: number[] = [];
    page.on("response", async (response) => {
      const request = response.request();
      if (
        request.method() !== "POST" ||
        new URL(response.url()).pathname !== "/api/v1/flows/"
      ) {
        return;
      }
      creates.push(response.status());
      if (response.ok()) created.push((await response.json()).id);
    });

    try {
      // A slow connection: the first click has not opened the canvas yet when
      // the second one lands.
      await page.route("**/api/v1/**", async (route) => {
        await new Promise((resolve) => setTimeout(resolve, 300));
        await route.fallback();
      });
      const newFlow = page.getByTestId("new-project-btn");
      await newFlow.click();
      await page.waitForTimeout(100);
      await newFlow.click({ timeout: TIMEOUTS.short }).catch(() => {});

      await expect(page).toHaveURL(/\/flow\//, { timeout: TIMEOUTS.standard });
      await page.unroute("**/api/v1/**");
      await expect(page.getByText("Name must be unique")).toHaveCount(0);

      expect(creates).toEqual([201]);
      expect(page.url()).toContain(`/flow/${created[0]}`);
    } finally {
      for (const id of created) {
        await page.request.delete(`/api/v1/flows/${id}`);
      }
    }
  },
);
