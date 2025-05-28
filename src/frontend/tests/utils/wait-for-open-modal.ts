import { Page } from "playwright/test";

export const waitForOpenModalWithChatInput = async (page: Page) => {
  await page.waitForSelector('[data-testid="input-chat-playground"]', {
    timeout: 10000,
  });
};

export const waitForOpenModalWithoutChatInput = async (page: Page) => {
  await page.waitForSelector('[data-testid="button-send"]', {
    timeout: 100000,
  });
};
