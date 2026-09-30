import { expect, test } from "../../fixtures";
import {
  createTextInputOutputFlow,
  freezePathFromTextOutput,
  runTextInputOutputFlow,
} from "../../utils/flow/text-input-output-flow";

test(
  "user must be able to freeze a component with the current graph state",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await createTextInputOutputFlow(page);
    expect(await runTextInputOutputFlow(page, "hello world")).toBe(
      "hello world",
    );
    await freezePathFromTextOutput(page, "toolbar");

    expect(await runTextInputOutputFlow(page, "ignored after freeze")).toBe(
      "hello world",
    );
  },
);
