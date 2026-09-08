import { expect, type LangflowPage, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";

// The flow settings modal is reached from the flow card's actions menu on the
// flows list, not from the canvas: FlowSettingsModal is mounted in
// pages/MainPage/components/list.
async function openFlowSettingsModal(page: LangflowPage) {
  await awaitBootstrapTest(page, { skipModal: true });
  await page.getByTestId("home-dropdown-menu").first().click();
  await page.getByTestId("btn-edit-flow").click();
  await expect(page.getByRole("dialog")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
}

test(
  "flow settings modal accessibility",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openFlowSettingsModal(page);
    await page.runA11yScan("flow-settings-modal");
  },
);

// Form.Field generates the id that Form.Label points at, and Form.Control
// forwards it to the input. A hardcoded id on the input silently overrode it,
// leaving every label in the modal pointing at an element that does not exist.
// Asserting the accessible name would NOT catch this: the inputs carry a
// placeholder, which the name computation falls back to even when the label
// is orphaned. Assert the association itself.
test(
  "flow settings labels resolve to their controls",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openFlowSettingsModal(page);

    const orphanedLabels = await page.evaluate(() => {
      const dialog = document.querySelector('[role="dialog"]');
      if (!dialog) {
        throw new Error("flow settings dialog not found");
      }
      return Array.from(dialog.querySelectorAll("label[for]"))
        .map((label) => label.getAttribute("for") as string)
        .filter((id) => !dialog.querySelector(`#${CSS.escape(id)}`));
    });

    expect(orphanedLabels).toEqual([]);
  },
);
