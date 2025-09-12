import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

function getRandomSocialMediaQuery(): string {
  const companies = [
    "OpenAI",
    "Microsoft",
    "Google",
    "Tesla",
    "Netflix",
    "Spotify",
    "Adobe",
    "Amazon",
    "Meta",
    "Apple",
  ];

  const platforms = [
    "TikTok",
    "Instagram",
    "Twitter",
    "LinkedIn",
    "YouTube",
    "Facebook",
  ];

  const contentTypes = [
    "latest video",
    "recent post",
    "profile bio",
    "latest update",
    "recent activity",
  ];

  const randomCompany = companies[Math.floor(Math.random() * companies.length)];
  const randomPlatform =
    platforms[Math.floor(Math.random() * platforms.length)];
  const randomContent1 =
    contentTypes[Math.floor(Math.random() * contentTypes.length)];
  let randomContent2 =
    contentTypes[Math.floor(Math.random() * contentTypes.length)];

  // Make sure we don't get the same content type twice
  while (randomContent1 === randomContent2) {
    randomContent2 =
      contentTypes[Math.floor(Math.random() * contentTypes.length)];
  }

  return `Find the ${randomPlatform} profile of the company ${randomCompany} using Google search, then show me the ${randomContent1} and their ${randomContent2}.`;
}

withEventDeliveryModes(
  "Social Media Agent",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.APIFY_API_TOKEN,
      "APIFY_API_TOKEN required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Social Media Agent" }).click();

    await initialGPTsetup(page);

    const apifyApiTokenInputCount = await page
      .getByTestId("popover-anchor-input-apify_token")
      .count();

    for (let i = 0; i < apifyApiTokenInputCount; i++) {
      await page
        .getByTestId("popover-anchor-input-apify_token")
        .nth(i)
        .fill(process.env.APIFY_API_TOKEN ?? "");
    }

    await page
      .getByTestId("popover-anchor-input-apify_token")
      .nth(apifyApiTokenInputCount - 1)
      .fill(process.env.APIFY_API_TOKEN ?? "");

    await page.getByTestId("playground-btn-flow-io").click();

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill(getRandomSocialMediaQuery());

    await page.getByTestId("button-send").last().click();

    const stopButton = page.getByRole("button", { name: "Stop" });
    await stopButton.waitFor({ state: "visible", timeout: 30000 });

    if (await stopButton.isVisible()) {
      await expect(stopButton).toBeHidden({ timeout: 120000 });
    }

    const output = await page
      .getByTestId("div-chat-message")
      .last()
      .innerText();

    expect(output.length).toBeGreaterThan(100);
  },
);
