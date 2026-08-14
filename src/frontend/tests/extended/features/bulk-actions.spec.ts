import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { openTemplatesModal } from "../../utils/flow/new-project-flow";

test(
  "user should be able to select flows with different methods and perform bulk actions",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Add some flows to test with
    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
    await adjustScreenView(page);

    // Go back to main page
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 100000,
    });
    await page.getByTestId("icon-ChevronLeft").first().click();

    await expect(page.getByText("Projects").first()).toBeVisible();
    await openTemplatesModal(page);
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Document Q&A" }).click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 100000,
    });
    await page.getByTestId("icon-ChevronLeft").first().click();

    await expect(page.getByText("Projects").first()).toBeVisible();
    await openTemplatesModal(page);
    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 100000,
    });
    await page.getByTestId("icon-ChevronLeft").first().click();

    await expect(page.getByText("Projects").first()).toBeVisible();
    await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
      timeout: 100000,
    });
    await expect(page.getByTestId("list-card").nth(2)).toBeVisible();

    // Test shift selection
    await page.keyboard.down("Shift");
    await page.getByTestId("list-card").first().click();
    await page.getByTestId("list-card").nth(2).click();
    await page.keyboard.up("Shift");

    // Verify both flows are selected
    const firstCheckbox = await page.getByTestId(/^checkbox-/).first();
    const secondCheckbox = await page.getByTestId(/^checkbox-/).nth(1);
    const thirdCheckbox = await page.getByTestId(/^checkbox-/).nth(2);
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
    await page.getByTestId("list-card").first().click();
    await page.keyboard.up("Shift");

    // Verify both flows are deselected
    await expect(firstCheckbox).not.toBeChecked();
    await expect(secondCheckbox).not.toBeChecked();
    await expect(thirdCheckbox).not.toBeChecked();

    // Test Ctrl/Cmd selection
    await page.keyboard.down("ControlOrMeta");
    await page.getByTestId("list-card").first().click();
    await page.getByTestId("list-card").nth(2).click();
    await page.keyboard.up("ControlOrMeta");

    // Verify both flows are selected again
    await expect(firstCheckbox).toBeChecked();
    await expect(secondCheckbox).not.toBeChecked();
    await expect(thirdCheckbox).toBeChecked();

    const flowNameElements = page
      .locator("[data-testid='flow-name-div']")
      .locator("[data-testid^='flow-name-']");
    const firstFlowTestId = await flowNameElements
      .first()
      .getAttribute("data-testid");
    const secondFlowTestId = await flowNameElements
      .nth(1)
      .getAttribute("data-testid");
    const thirdFlowTestId = await flowNameElements
      .nth(2)
      .getAttribute("data-testid");
    expect(firstFlowTestId).toMatch(/^flow-name-/);
    expect(secondFlowTestId).toMatch(/^flow-name-/);
    expect(thirdFlowTestId).toMatch(/^flow-name-/);

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
    await expect(page.getByTestId(firstFlowTestId!)).toHaveCount(0);
    await expect(page.getByTestId(secondFlowTestId!)).toBeVisible();
    await expect(page.getByTestId(thirdFlowTestId!)).toHaveCount(0);
  },
);
