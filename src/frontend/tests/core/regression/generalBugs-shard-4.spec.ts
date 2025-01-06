import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "should be able to move flow from folder, rename it and be displayed on correct folder",
  { tag: ["@release"] },
  async ({ page }) => {
    test.skip(
      true,
      "this functionality doesn't work yet w/ the uplift designs",
    );
    const randomName = Math.random().toString(36).substring(2);
    const secondRandomName = Math.random().toString(36).substring(2);

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Vector Store RAG" })
      .first()
      .click();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();

    await page.getByTestId("flow-configuration-button").click();
    await page.getByText("Flow Settings").click();
    await page.getByPlaceholder("Flow name").fill(randomName);
    await page.getByText("Save").last().click();
    await page.getByTestId("icon-ChevronLeft").last().click();

    await page.getByTestId("add-folder-button").click();

    let countFolders = await page.getByText("New Folder").count();

    while (countFolders > 1) {
      await page.getByText("New Folder").first().hover();

      await page.getByTestId("more-options-button").first().click();
      await page.getByTestId("btn-delete-folder").click();
      await page.getByText("Delete").last().click();
      countFolders--;
      await page.waitForTimeout(1000);
    }

    // Get the bounding boxes of the elements
    const sourceElement = await page.getByTestId(`card-${randomName}`).first();
    const targetElement = await page.getByText("New Folder").last();

    const sourceBox = await sourceElement.boundingBox();
    const targetBox = await targetElement.boundingBox();

    // Perform the drag and drop
    await page.mouse.move(
      sourceBox!.x + sourceBox!.width / 2,
      sourceBox!.y + sourceBox!.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      targetBox!.x + targetBox!.width / 2,
      targetBox!.y + targetBox!.height / 2,
    );
    await page.mouse.up();

    await page.waitForTimeout(3000);

    await page.getByText("New Folder").last().click();

    expect(await page.getByTestId(`card-${randomName}`).first().isVisible());

    await page.getByTestId(`card-${randomName}`).first().click();

    await page.getByTestId("flow-configuration-button").click();
    await page.getByText("Flow Settings").click();
    await page.getByPlaceholder("Flow name").fill(secondRandomName);
    await page.getByText("Save").last().click();
    await page.getByTestId("icon-ChevronLeft").last().click();

    await page.waitForTimeout(3000);

    await page.getByText("New Folder").last().click();
    expect(
      await page.getByTestId(`card-${secondRandomName}`).first().isVisible(),
    );

    // Get the bounding boxes of the elements
    const secondSourceElement = await page
      .getByTestId(`card-${secondRandomName}`)
      .first();
    const secondTargetElement = await page.getByText("New Folder").last();

    const secondSourceBox = await secondSourceElement.boundingBox();
    const secondTargetBox = await secondTargetElement.boundingBox();

    // Perform the drag and drop
    await page.mouse.move(
      secondSourceBox!.x + secondSourceBox!.width / 2,
      secondSourceBox!.y + secondSourceBox!.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      secondTargetBox!.x + secondTargetBox!.width / 2,
      secondTargetBox!.y + secondTargetBox!.height / 2,
    );
    await page.mouse.up();

    await page.waitForTimeout(3000);

    await page.getByText("My Projects").last().click();

    expect(
      await page.getByTestId(`card-${secondRandomName}`).first().isVisible(),
    );
  },
);
