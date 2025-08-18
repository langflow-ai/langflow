import type { Page } from "playwright/test";

export const buildDataTransfer = async (page: Page, fileContent: string) => {
  return await page.evaluateHandle(
    ({ fileContent }) => {
      const dt = new DataTransfer();
      const byteCharacters = atob(fileContent);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const file = new File([byteArray], "chain.png", { type: "image/png" });
      dt.items.add(file);
      return dt;
    },
    { fileContent },
  );
};
