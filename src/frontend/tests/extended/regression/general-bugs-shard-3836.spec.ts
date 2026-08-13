import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TEXTS } from "../../utils/constants/texts";
import {
  closeParametersPanel,
  openParametersPanel,
  toggleParameterOnNode,
} from "../../utils/open-advanced-options";
import { uploadFile } from "../../utils/upload-file";

test(
  "user must be able to send an image on chat using advanced tool on ChatInputComponent",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
    await configureLoopbackOpenAI(page);

    await page.waitForSelector("text=Chat Input", { timeout: 30000 });

    await page.getByRole("group", { name: "Chat Input node" }).click();
    // LE-1810: the parameters panel adds the hidden files field to the node
    await openParametersPanel(page);
    await toggleParameterOnNode(page, "files");
    await closeParametersPanel(page);
    const userQuestion = "What is this image?";
    await page.getByTestId("textarea_str_input_value").fill(userQuestion);

    await uploadFile(page, "chain.png");

    const uploadButton = page.getByTestId("button_upload_file");

    await uploadButton.hover();
    await expect(uploadButton.getByTestId("icon-X")).toHaveCSS("opacity", "1");
    await uploadButton.click();
    await expect(page.getByText("chain.png")).not.toBeVisible();

    await uploadFile(page, "chain.png");

    await page.getByTestId("button_run_chat output").click();

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    // await page.waitForSelector("text=chain.png", { timeout: 30000 });

    // expect(await page.getByAltText("generated image").isVisible()).toBeTruthy();

    await expect(page.locator('img[alt$="chain.png"]')).toBeVisible({
      timeout: 100000,
    });

    expect(
      await page.getByTestId(`chat-message-User-${userQuestion}`).isVisible(),
    ).toBeTruthy();
  },
);
