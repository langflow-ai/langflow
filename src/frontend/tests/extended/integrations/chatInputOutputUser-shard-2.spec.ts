import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "user must interact with chat with Input/Output",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await initialGPTsetup(page);

    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    await page.getByTestId("input-chat-playground").fill("Hello, how are you?");

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").click();
    let valueUser = await page.getByTestId("sender_name_user").textContent();

    await page.waitForSelector('[data-testid="sender_name_ai"]', {
      timeout: 100000,
    });

    let valueAI = await page.getByTestId("sender_name_ai").textContent();

    expect(valueUser).toBe("User");
    expect(valueAI).toContain("AI");

    await page.keyboard.press("Escape");

    await page
      .getByTestId("textarea_str_input_value")
      .nth(0)
      .fill(
        "testtesttesttesttesttestte;.;.,;,.;,.;.,;,..,;;;;;;;;;;;;;;;;;;;;;,;.;,.;,.,;.,;.;.,~~çççççççççççççççççççççççççççççççççççççççisdajfdasiopjfaodisjhvoicxjiovjcxizopjviopasjioasfhjaiohf23432432432423423sttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttestççççççççççççççççççççççççççççççççç,.,.,.,.,.,.,.,.,.,.,.,.,.,.,.,.,!",
      );
    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").click();
    await page.getByText("Close", { exact: true }).click();
    await page.getByText("Chat Input", { exact: true }).click();
    await page.getByTestId("edit-button-modal").click();
    await page.getByTestId("showsender_name").click();
    await page.getByText("Close").last().click();

    await page.getByText("Chat Output", { exact: true }).click();
    await page.getByTestId("edit-button-modal").click();
    await page.getByTestId("showsender_name").click();
    await page.getByText("Close").last().click();

    await page
      .getByTestId("popover-anchor-input-sender_name")
      .nth(1)
      .fill("TestSenderNameUser");
    await page
      .getByTestId("popover-anchor-input-sender_name")
      .nth(0)
      .fill("TestSenderNameAI");

    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").click();

    valueUser = await page
      .getByTestId("sender_name_testsendernameuser")
      .textContent();
    valueAI = await page
      .getByTestId("sender_name_testsendernameai")
      .textContent();

    expect(valueUser).toContain("TestSenderNameUser");
    expect(valueAI).toContain("TestSenderNameAI");

    expect(
      await page
        .getByText(
          "testtesttesttesttesttestte;.;.,;,.;,.;.,;,..,;;;;;;;;;;;;;;;;;;;;;,;.;,.;,.,;.,;.;.,~~çççççççççççççççççççççççççççççççççççççççisdajfdasiopjfaodisjhvoicxjiovjcxizopjviopasjioasfhjaiohf23432432432423423sttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttestççççççççççççççççççççççççççççççççç,.,.,.,.,.,.,.,.,.,.,.,.,.,.,.,.,!",
          { exact: true },
        )
        .isVisible(),
    );
  },
);
