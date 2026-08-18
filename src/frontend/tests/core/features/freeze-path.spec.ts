import { expect, test } from "../../fixtures";
import {
  createTextInputOutputFlow,
  freezePathFromTextOutput,
  runTextInputOutputFlow,
} from "../../utils/flow/text-input-output-flow";

test(
  "user must be able to freeze a deterministic input-to-output path",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await createTextInputOutputFlow(page);

    expect(await runTextInputOutputFlow(page, "first value")).toBe(
      "first value",
    );
    expect(await runTextInputOutputFlow(page, "cached value")).toBe(
      "cached value",
    );

    await freezePathFromTextOutput(page, "menu");

    expect(await runTextInputOutputFlow(page, "post-freeze value")).toBe(
      "cached value",
    );
  },
);
