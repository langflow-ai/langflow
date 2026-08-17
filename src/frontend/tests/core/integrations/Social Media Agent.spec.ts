import { expect } from "../../fixtures";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { configureLoopbackWebSearch } from "../../utils/configure-loopback-web-search";
import { TEXTS } from "../../utils/constants/texts";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";
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
    await seedLoopbackProvider(page);
    await openStarterProject(page, "Social Media Agent");

    await configureLoopbackOpenAI(page);
    await configureLoopbackWebSearch(page);

    await page.getByTestId("playground-btn-flow-io").click();

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill(getRandomSocialMediaQuery());

    await page.getByTestId("button-send").last().click();

    const stopButton = page.getByRole("button", { name: TEXTS.stop });
    await stopButton.waitFor({ state: "visible", timeout: 30000 });

    if (await stopButton.isVisible()) {
      await expect(stopButton).toBeHidden({ timeout: 120000 });
    }

    const output = await page
      .getByTestId("div-chat-message")
      .last()
      .innerText();

    expect(output.length).toBeGreaterThan(100);
    expect(output).toContain("LOOPBACK_WEB_SEARCH_USED");
  },
);
