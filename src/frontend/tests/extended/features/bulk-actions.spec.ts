import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import {
  openTemplatesModal,
  waitForNewProjectButton,
} from "../../utils/flow/new-project-flow";
import { selectStarterTemplate } from "../../utils/flow/select-starter-template";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";
import { waitForMainPageReady } from "../../utils/flow/wait-for-main-page-ready";

test(
  "user should be able to select flows with different methods and perform bulk actions",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const returnToHome = async () => {
      await page.goto("/");
      await waitForMainPageReady(page);
      await waitForNewProjectButton(page);
    };

    await awaitBootstrapTest(page);

    // Add some flows to test with
    const firstFlowId = await selectStarterTemplate(
      page,
      TEXTS.templateBasicPrompting,
    );
    await waitForFlowEditorReady(page);

    await returnToHome();

    await openTemplatesModal(page);
    const secondFlowId = await selectStarterTemplate(page, "Document Q&A");
    await waitForFlowEditorReady(page);
    await returnToHome();

    await openTemplatesModal(page);
    const thirdFlowId = await selectStarterTemplate(
      page,
      TEXTS.templateBasicPrompting,
    );
    await waitForFlowEditorReady(page);
    await returnToHome();

    await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
      timeout: 100000,
    });
    const getFlowCard = (flowId: string) =>
      page
        .getByTestId("list-card")
        .filter({ has: page.getByTestId(`flow-name-${flowId}`) });
    const firstCard = getFlowCard(firstFlowId);
    const secondCard = getFlowCard(secondFlowId);
    const thirdCard = getFlowCard(thirdFlowId);
    await expect(firstCard).toBeVisible();
    await expect(secondCard).toBeVisible();
    await expect(thirdCard).toBeVisible();

    // Test shift selection
    await page.keyboard.down("Shift");
    await firstCard.getByTestId("list-card-open-button").click();
    await thirdCard.getByTestId("list-card-open-button").click();
    await page.keyboard.up("Shift");

    // Verify both flows are selected
    const firstCheckbox = page.getByTestId(`checkbox-${firstFlowId}`);
    const secondCheckbox = page.getByTestId(`checkbox-${secondFlowId}`);
    const thirdCheckbox = page.getByTestId(`checkbox-${thirdFlowId}`);
    await expect(firstCheckbox).toBeChecked();
    await expect(secondCheckbox).toBeChecked();
    await expect(thirdCheckbox).toBeChecked();
    // Test bulk download
    await page.getByTestId("download-bulk-btn").last().click();
    await expect(page.getByText(/.*downloaded successfully/)).toBeVisible({
      timeout: 10000,
    });

    // Deselect all
    await page.keyboard.down("Shift");
    await firstCard.getByTestId("list-card-open-button").click();
    await page.keyboard.up("Shift");

    // Verify both flows are deselected
    await expect(firstCheckbox).not.toBeChecked();
    await expect(secondCheckbox).not.toBeChecked();
    await expect(thirdCheckbox).not.toBeChecked();

    // Test Ctrl/Cmd selection
    await page.keyboard.down("ControlOrMeta");
    await firstCard.getByTestId("list-card-open-button").click();
    await thirdCard.getByTestId("list-card-open-button").click();
    await page.keyboard.up("ControlOrMeta");

    // Verify both flows are selected again
    await expect(firstCheckbox).toBeChecked();
    await expect(secondCheckbox).not.toBeChecked();
    await expect(thirdCheckbox).toBeChecked();

    // Test bulk delete
    await page.getByTestId("delete-bulk-btn").first().click();
    await page.getByText("This can't be undone.").isVisible({
      timeout: 1000,
    });
    await page.getByText(TEXTS.delete).last().click();

    // Verify deletion success message
    await expect(page.getByText("Flows deleted successfully")).toBeVisible({
      timeout: 10000,
    });

    // Verify flows are deleted
    await expect(page.getByTestId(`flow-name-${firstFlowId}`)).toHaveCount(0);
    await expect(page.getByTestId(`flow-name-${secondFlowId}`)).toBeVisible();
    await expect(page.getByTestId(`flow-name-${thirdFlowId}`)).toHaveCount(0);
  },
);
