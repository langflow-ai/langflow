import { test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { openTemplatesModal } from "../../utils/flow/new-project-flow";
import { routeTestScopedDefaultFlowNames } from "../../utils/flow/route-test-scoped-default-flow-names";

test.beforeEach(async ({ page }, testInfo) => {
  await routeTestScopedDefaultFlowNames(page, testInfo, "auto-login");
});

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
        await page.goto("/login/admin");
        await openTemplatesModal(page);
      },
    );
  },
);
