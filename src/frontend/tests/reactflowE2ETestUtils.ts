export const offsetElements = async ({
    sourceElement,
    targetElement,
    page,
  }) => {
    // Get bounding boxes
    const box1 = await sourceElement.boundingBox();
    const box2 = await targetElement.boundingBox();

    await page.mouse.move((box2?.x || 0) + 5, (box2?.y || 0) + 5);
    await page.mouse.down();

    // Move to the right of the source element
    await page.mouse.move(
      (box2?.x || 0) + (box2?.width || 0) / 2 + (box1?.width || 0),
      box2?.y || 0,
    );
    await page.mouse.up();
  };

  export const focusElementsOnBoard = async ({ page }) => {
    const focusElements = await page.locator(
      '//*[@id="react-flow-id"]/div/div[2]/button[3]',
    );
    focusElements.click();
  };
