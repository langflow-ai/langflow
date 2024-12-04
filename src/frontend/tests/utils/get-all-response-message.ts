import { Page } from "playwright/test";

export const getAllResponseMessage = async (page: Page) => {
  const numberOfResponseMessages = await page
    .getByTestId("div-chat-message")
    .count();

  const textContents: string[] = [];
  for (let i = 0; i < numberOfResponseMessages; i++) {
    const textContent = await page
      .getByTestId("div-chat-message")
      .nth(i)
      .textContent();

    if (textContent) {
      textContents.push(textContent);
    }
  }

  return textContents.join(" ").toLowerCase();
};
