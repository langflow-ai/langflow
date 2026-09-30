import { expect, type Page, type Response } from "@playwright/test";
import { TEXTS } from "../../utils/constants/texts";
import { TID } from "../constants/testIds";

type FlowPatchPayload = {
  data?: {
    nodes?: Array<{
      data?: {
        node?: {
          template?: {
            code?: { value?: unknown };
          };
        };
      };
    }>;
  };
};

function isCodeValidationResponse(response: Response, code: string): boolean {
  if (
    response.request().method() !== "POST" ||
    !new URL(response.url()).pathname.endsWith("/api/v1/custom_component")
  ) {
    return false;
  }

  const requestPayload = response.request().postDataJSON() as {
    code?: unknown;
  };
  return requestPayload.code === code;
}

function isFlowPatchPersistingCode(response: Response, code: string): boolean {
  if (
    response.request().method() !== "PATCH" ||
    !/\/api\/v1\/flows\/[^/]+$/.test(new URL(response.url()).pathname)
  ) {
    return false;
  }

  const requestPayload = response.request().postDataJSON() as FlowPatchPayload;
  return Boolean(
    requestPayload.data?.nodes?.some(
      (node) => node.data?.node?.template?.code?.value === code,
    ),
  );
}
/**
 * Replace the code of the currently-selected custom component.
 *
 * Replaces the 5-step ritual that appears in 3+ specs:
 *   1. click code-button-modal
 *   2. click .ace_content
 *   3. ControlOrMeta+A (select all)
 *   4. textarea.fill(code)
 *   5. click "Check & Save"
 *
 * Returns only after the matching code-validation request and the debounced
 * flow PATCH containing that code have both completed successfully.
 *
 * The caller is responsible for selecting the target node first.
 */
export async function replaceComponentCode(
  page: Page,
  code: string,
): Promise<void> {
  await page.getByTestId(TID.codeButtonModal).first().click();
  await page.locator(".ace_content").click();
  await page.keyboard.press("ControlOrMeta+A");
  await page.locator("textarea").fill(code);

  const validationResponsePromise = page.waitForResponse((response) =>
    isCodeValidationResponse(response, code),
  );
  const persistenceResponsePromise = page.waitForResponse((response) =>
    isFlowPatchPersistingCode(response, code),
  );
  await page.getByText(TEXTS.checkAndSave).last().click();

  const validationResponse = await validationResponsePromise;
  expect(validationResponse.ok()).toBeTruthy();
  expect(await validationResponse.finished()).toBeNull();

  const persistenceResponse = await persistenceResponsePromise;
  expect(persistenceResponse.ok()).toBeTruthy();
  expect(await persistenceResponse.finished()).toBeNull();
}
