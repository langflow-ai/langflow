import { test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
test.describe(
  "Auto_login tests",
  { tag: ["@release", "@api", "@database"] },

  () => {
    test(
      "auto_login sign in",
      { tag: ["@release", "@api", "@database"] },
      async ({ page }) => {
        await awaitBootstrapTest(page, {
          skipModal: true,
        });
        await page.getByText("New Flow", { exact: true }).click();
      },
    );

    test(
      "auto_login block_admin",
      { tag: ["@release", "@api", "@database"] },
      async ({ page }) => {
        await awaitBootstrapTest(page, {
          skipModal: true,
        });
        await page.getByText("New Flow", { exact: true }).click();
        await page.waitForSelector('[data-testid="modal-title"]', {
          timeout: 5000,
        });

        await page.goto("/login");
        await page.getByText("New Flow", { exact: true }).click();
        await page.waitForSelector('[data-testid="modal-title"]', {
          timeout: 5000,
        });
        await page.goto("/admin");
        await page.getByText("New Flow", { exact: true }).click();
        await page.waitForSelector('[data-testid="modal-title"]', {
          timeout: 5000,
        });

        await page.goto("/admin/login");
        await page.getByText("New Flow", { exact: true }).click();
        await page.waitForSelector('[data-testid="modal-title"]', {
          timeout: 5000,
        });
      },
    );
  },
);
