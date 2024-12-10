import { Page } from "@playwright/test";
import { readFileSync } from "fs";

export async function simulateDragAndDrop(
  page: Page,
  filePath: string,
  jsonContent?: string,
) {
  // Read file content
  let fileContent = await readFileSync(filePath, "utf-8");

  if (jsonContent) {
    fileContent = jsonContent;
  }

  // Create DataTransfer object with file
  const dataTransfer = await page.evaluateHandle(async (content) => {
    const dt = new DataTransfer();
    const file = new File([content], "file.json", { type: "application/json" });
    dt.items.add(file);
    return dt;
  }, fileContent);

  return dataTransfer;
}
