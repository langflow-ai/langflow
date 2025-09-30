import * as dotenv from "dotenv";
import path from "path";
import { test } from "../../fixtures";

test(
  "should delete a flow (requires store API key)",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.STORE_API_KEY,
      "STORE_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }
    await page.goto("/");
    await page.waitForTimeout(1000);

    await page.getByTestId("button-store").click();
    await page.waitForTimeout(1000);

    await page.getByTestId("api-key-button-store").click({
      timeout: 200000,
    });

    await page
      .getByPlaceholder("Insert your API Key")
      .fill(process.env.STORE_API_KEY ?? "");

    await page.getByTestId("api-key-save-button-store").click();

    await page.waitForTimeout(1000);
    await page.getByText("Success! Your API Key has been saved.").isVisible();

    await page.waitForSelector('[data-testid="button-store"]', {
      timeout: 30000,
    });

    await page.getByTestId("button-store").click();
    await page.waitForLoadState("networkidle");

    // Get and click install button
    const installButton = await waitForInstallButton(page);
    await installButton.click();

    // Handle success message
    await waitForSuccessMessage(page);

    // Wait for navigation button
    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      state: "visible",
      timeout: 30000,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector("text=Website Content QA", { timeout: 30000 });

    await page.getByText("Website Content QA").first().isVisible();

    await page.getByTestId("home-dropdown-menu").first().click();
    await page.waitForTimeout(500);

    await page.getByText("Delete").last().click();
    await page.waitForTimeout(500);
    await page
      .getByText("Are you sure you want to delete the selected component?")
      .isVisible();
    await page.getByText("Delete").nth(1).click();
    await page.waitForTimeout(1000);
    await page.getByText("Successfully").first().isVisible();
  },
);

async function waitForInstallButton(page) {
  try {
    // Wait for install button with retry logic
    const button = await page.waitForSelector(
      '[data-testid="install-Website Content QA"]',
      {
        state: "visible",
        timeout: 100000,
      },
    );

    // Ensure button is ready for interaction
    await button.waitForElementState("stable");
    return button;
  } catch (error) {
    console.error("Install button not found, retrying...");
    // Optional: Add custom retry logic here
    throw error;
  }
}

async function waitForSuccessMessage(page) {
  try {
    // Wait for success message
    await page.waitForSelector('text="Flow Installed Successfully."', {
      state: "visible",
      timeout: 30000,
    });

    // Click the message when it's ready
    await page.getByText("Flow Installed Successfully.").first().click();
  } catch (error) {
    console.error("Success message not found");
    throw error;
  }
}
