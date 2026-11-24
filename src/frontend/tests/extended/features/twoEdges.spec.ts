import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

import { TEXTS } from "../../utils/constants/texts";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";

test(
  "user should be able to see multiple edges and interact with them",
  { tag: ["@release", "@api", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByText("Vector Store RAG", { exact: true }).last().click();
    await waitForFlowEditorReady(page);
    // Fit the view before asserting on nodes. The template opens with a
    // viewport that does not necessarily contain every node, and a node
    // outside it is mounted but reports hidden -- which is how this test
    // failed its first attempt with Knowledge "resolved to <span ...> ...
    // unexpected value hidden". No zoom-out: the assertions below only need
    // the nodes inside the viewport, and the existing fit_view further down
    // re-fits anyway.
    await adjustScreenView(page, { numberOfZoomOut: 0 });
    // The post-Knowledge-merge Vector Store RAG template uses a single
    // Knowledge node instead of separate Retriever / Search Results nodes,
    // so assert against display_names that ARE in the current template.
    await expect(
      page.getByText("Knowledge", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      page.getByText(TEXTS.componentLanguageModel, { exact: true }).first(),
    ).toBeVisible();
    await page.getByTestId("canvas_controls_dropdown").click();

    const focusElementsOnBoard = async ({ page }) => {
      await page.waitForSelector('[data-testid="fit_view"]', {
        timeout: 30000,
      });
      const focusElements = await page.getByTestId("fit_view");
      await focusElements.click();
    };

    await focusElementsOnBoard({ page });
    await page.getByTestId("canvas_controls_dropdown").click({ force: true });

    await page.getByText("Knowledge", { exact: true }).first().isHidden();
    await expect(page.getByTestId("icon-ChevronDown").last()).toBeVisible();
    await page.getByTestId("icon-ChevronDown").last().click();
    await expect(
      page.getByText("Knowledge", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      page.getByText(TEXTS.componentLanguageModel, { exact: true }).first(),
    ).toBeVisible();
  },
);
