import type { Locator, Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";

async function addChromaNode(page: Page) {
  await openBlankFlow(page);
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("Chroma");

  await page.waitForSelector('[data-testid="chromaChroma DB"]', {
    timeout: 3000,
  });
  await page
    .getByTestId("chromaChroma DB")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await adjustScreenView(page);
}

async function composeAccent(page: Page, input: Locator) {
  const client = await page.context().newCDPSession(page);

  await input.click();
  await client.send("Input.imeSetComposition", {
    text: "´",
    selectionStart: 1,
    selectionEnd: 1,
    replacementStart: 0,
    replacementEnd: 0,
  });
  await client.send("Input.imeSetComposition", {
    text: "á",
    selectionStart: 1,
    selectionEnd: 1,
    replacementStart: 0,
    replacementEnd: 1,
  });
}

async function composeKorean(page: Page, input: Locator) {
  const client = await page.context().newCDPSession(page);

  await input.click();
  await client.send("Input.imeSetComposition", {
    text: "ㅎ",
    selectionStart: 1,
    selectionEnd: 1,
    replacementStart: 0,
    replacementEnd: 0,
  });
  await client.send("Input.imeSetComposition", {
    text: "하",
    selectionStart: 1,
    selectionEnd: 1,
    replacementStart: 0,
    replacementEnd: 1,
  });
}

test(
  "node input preserves IME composition",
  { tag: ["@release", "@workspace", "@regression"] },
  async ({ page }) => {
    await addChromaNode(page);

    const collectionNameInput = page.getByTestId(
      "popover-anchor-input-collection_name",
    );

    await collectionNameInput.fill("");
    await expect(collectionNameInput).toHaveValue("");

    await composeAccent(page, collectionNameInput);

    await expect(collectionNameInput).toHaveValue("á");
    await page.getByTestId("div-generic-node").click();
    await expect(collectionNameInput).toHaveValue("á");

    await collectionNameInput.fill("");
    await expect(collectionNameInput).toHaveValue("");

    await composeKorean(page, collectionNameInput);

    await expect(collectionNameInput).toHaveValue("하");

    await page.getByTestId("div-generic-node").click();
    await expect(collectionNameInput).toHaveValue("하");
  },
);
