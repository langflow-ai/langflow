import type { Page } from "playwright/test";

export const evaluateReactStateChanges = async (
  page: Page,
  selector: string,
  value: string,
) => {
  await page.evaluate(
    ({ selector, value }) => {
      const inputElement = document.querySelector(selector) as HTMLInputElement;
      if (inputElement) {
        const prototype = Object.getPrototypeOf(inputElement);
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
          prototype,
          "value",
        )?.set;
        if (nativeInputValueSetter) {
          nativeInputValueSetter.call(inputElement, value);
          inputElement.dispatchEvent(new Event("input", { bubbles: true }));
        }
      }
    },
    { selector, value },
  );
};
