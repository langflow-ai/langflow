import { test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test.skip("should be able to share a component on the store by clicking on the share button on the canvas", async ({
  page,
}) => {
  test.skip(
    !process?.env?.STORE_API_KEY,
    "STORE_API_KEY required to run this test",
  );

  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  }

  await page.goto("/");
  await page.waitForTimeout(1000);

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByText("Close", { exact: true }).click();

  await page.waitForTimeout(1000);

  await page.getByTestId("user-profile-settings").click();
  await page.waitForTimeout(500);

  await page.getByText("Settings", { exact: true }).first().click();

  await page.waitForTimeout(1000);

  await page
    .getByPlaceholder("Insert your API Key")
    .fill(process.env.STORE_API_KEY ?? "");

  await page.getByTestId("api-key-save-button-store").click();

  await page.waitForTimeout(1000);

  await page.getByText("Success! Your API Key has been saved.").isVisible();

  await page.waitForTimeout(1000);

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();
  await page.waitForTimeout(1000);

  await page.getByText("New Flow", { exact: true }).click();

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();
  await page.waitForSelector("text=share", { timeout: 10000 });
  await page.waitForSelector("text=playground", { timeout: 10000 });
  await page.waitForSelector("text=api", { timeout: 10000 });

  await page.getByTestId("shared-button-flow").click();

  await page.waitForTimeout(500);

  await page.waitForSelector("text=Share Flow", {
    timeout: 10000,
  });
  await page.waitForSelector('[data-testid="shared-button-flow"]', {
    timeout: 10000,
  });
  await page.waitForSelector("text=Share Flow", { timeout: 10000 });

  await page.getByTestId("share-modal-button-flow").click();

  let replace = await page.getByTestId("replace-button").isVisible();

  if (replace) {
    await page.getByTestId("replace-button").click();
  }

  await page.waitForSelector("text=flow shared successfully ", {
    timeout: 10000,
  });

  await page.waitForTimeout(500);

  await page.waitForSelector("text=share", { timeout: 10000 });
  await page.waitForSelector("text=playground", { timeout: 10000 });
  await page.waitForSelector("text=api", { timeout: 10000 });

  await page.getByTestId("shared-button-flow").click();

  await page.waitForTimeout(500);

  await page.waitForSelector("text=Publish workflow to the Langflow Store.", {
    timeout: 10000,
  });
  await page.waitForSelector('[data-testid="shared-button-flow"]', {
    timeout: 10000,
  });
  await page.waitForSelector("text=Share Flow", { timeout: 10000 });

  await page.getByTestId("share-modal-button-flow").click();

  replace = await page.getByTestId("replace-button").isVisible();

  if (replace) {
    await page.getByTestId("replace-button").click();
  }

  await page.waitForSelector("text=flow shared successfully ", {
    timeout: 10000,
  });
});
