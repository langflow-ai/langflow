import { expect, Page, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// TODO: This component doesn't have slider needs updating
test(
  "user should be able to use query input",
  {
    tag: ["@release", "@workspace"],
  },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("openai");

    await page.waitForSelector('[data-testid="openaiOpenAI"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("openaiOpenAI")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await page.getByTestId("fit_view").click();

    await page.getByTestId("title-OpenAI").click();
    await page.getByTestId("code-button-modal").click();

    let cleanCode = await extractAndCleanCode(page);

    // Replace the multiline string in the code
    let newCode = cleanCode.replace(
      `StrInput(
            name="openai_api_base",
            display_name="OpenAI API Base",
            advanced=True,
            info="The base URL of the OpenAI API. "
            "Defaults to https://api.openai.com/v1. "
            "You can change this to use other APIs like JinaChat, LocalAI and Prem.",
        ),`,
      `QueryInput(
            name="openai_api_base",
            display_name="OpenAI API Base",
            advanced=False,
            info="THIS IS A TEST INFORMATION TO DISPLAY",
            placeholder="THIS IS A TEST PLACEHOLDER",
        ),`,
    );

    newCode = newCode.replace(
      `from langflow.inputs.inputs import BoolInput, DictInput, DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput`,
      `from langflow.inputs.inputs import BoolInput, DictInput, DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput, QueryInput`,
    );

    // make sure codes are different
    expect(cleanCode).not.toEqual(newCode);
    await page.locator("textarea").last().press(`ControlOrMeta+a`);
    await page.keyboard.press("Backspace");
    await page.locator("textarea").last().fill(newCode);
    await page.locator('//*[@id="checkAndSaveBtn"]').click();

    await page.getByTestId("fit_view").click();

    await page
      .getByTestId("query_query_openai_api_base")
      .fill("THIS IS A TEST VALUE");

    await page
      .getByTestId("button_open_text_area_modal_query_query_openai_api_base")
      .click();

    expect(await page.getByTestId("text-area-modal").inputValue()).toEqual(
      "THIS IS A TEST VALUE",
    );
    expect(
      await page.getByText("THIS IS A TEST INFORMATION TO DISPLAY").isVisible(),
    ).toBeTruthy();

    await page.getByTestId("text-area-modal").fill("THIS IS A NEW VALUE");

    await page.getByTestId("genericModalBtnSave").click();

    expect(
      await page.getByTestId("query_query_openai_api_base").inputValue(),
    ).toEqual("THIS IS A NEW VALUE");

    await page.getByTestId("edit-button-modal").click();

    expect(
      await page.getByTestId("query_query_edit_openai_api_base").inputValue(),
    ).toEqual("THIS IS A NEW VALUE");

    await page
      .getByTestId(
        "button_open_text_area_modal_query_query_edit_openai_api_base_advanced",
      )
      .click();

    await page
      .getByTestId("text-area-modal")
      .fill("THIS IA TEST TEXT INSIDE CONTROLS PANEL");

    await page.getByTestId("genericModalBtnSave").click();

    expect(
      await page.getByTestId("query_query_edit_openai_api_base").inputValue(),
    ).toEqual("THIS IA TEST TEXT INSIDE CONTROLS PANEL");

    await page.getByText("Close").last().click();

    expect(
      await page.getByTestId("query_query_openai_api_base").inputValue(),
    ).toEqual("THIS IA TEST TEXT INSIDE CONTROLS PANEL");
  },
);

async function extractAndCleanCode(page: Page): Promise<string> {
  const outerHTML = await page
    .locator('//*[@id="codeValue"]')
    .evaluate((el) => el.outerHTML);

  const valueMatch = outerHTML.match(/value="([\s\S]*?)"/);
  if (!valueMatch) {
    throw new Error("Could not find value attribute in the HTML");
  }

  let codeContent = valueMatch[1]
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#x27;/g, "'")
    .replace(/&#x2F;/g, "/");

  return codeContent;
}
