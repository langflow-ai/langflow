import type { Locator, Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";

async function addTextInputNode(page: Page) {
  await openBlankFlow(page);
  await addLegacyComponents(page);
  await addComponentFromSidebar(page, {
    search: "text input",
    testId: "input_outputText Input",
    hoverAdd: true,
  });
  await expect(
    page.getByRole("application", { name: "Text Input node" }),
  ).toHaveCount(1);
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
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await addTextInputNode(page);

    const textInput = page.getByTestId("textarea_str_input_value");

    await textInput.fill("");
    await expect(textInput).toHaveValue("");

    await composeAccent(page, textInput);

    await expect(textInput).toHaveValue("á");
    await page.getByTestId("div-generic-node").click();
    await expect(textInput).toHaveValue("á");

    await textInput.fill("");
    await expect(textInput).toHaveValue("");

    await composeKorean(page, textInput);

    await expect(textInput).toHaveValue("하");

    await page.getByTestId("div-generic-node").click();
    await expect(textInput).toHaveValue("하");
  },
);
