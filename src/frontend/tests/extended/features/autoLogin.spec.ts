import { test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { openTemplatesModal } from "../../utils/flow/new-project-flow";

test.describe(
  "Auto_login tests",
  { tag: ["@release", "@api", "@database", "@mainpage"] },

  () => {
    test(
      "auto_login sign in",
      { tag: ["@release", "@api", "@database"] },
      async ({ page }) => {
        await awaitBootstrapTest(page, {
          skipModal: true,
        });
        await openTemplatesModal(page);
      },
    );

    test(
      "auto_login block_admin",
      { tag: ["@release", "@api", "@database"] },
      async ({ page }) => {
        await awaitBootstrapTest(page, {
          skipModal: true,
        });
        await openTemplatesModal(page);

        await page.goto("/login");
        await openTemplatesModal(page);
        await page.goto("/admin");
        await openTemplatesModal(page);

        await page.goto("/admin/login");
        await openTemplatesModal(page);
      },
    );
  },
);
