import { Page } from "@playwright/test";

export const selectOutput = async (
  page: Page,
  inputId: string,
  outputId: string,
) => {
  // Get the input handle element
  const inputHandle = await page.getByTestId(inputId);

  // If input handle is visible, click it directly
  if (await inputHandle.isVisible()) {
    await inputHandle.nth(0).click();
    await page.getByTestId(outputId).click();
  } else {
    // Otherwise find and click the corresponding output handle
    const outputSelector = inputId.replace("handle", "output");
    const outputHandle = await page.getByTestId(outputSelector);

    // Click both handles to establish connection
    await outputHandle.click();
    await page.getByTestId(outputId).click();
  }
};
