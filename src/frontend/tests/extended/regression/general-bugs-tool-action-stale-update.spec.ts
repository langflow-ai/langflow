import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

const NEW_SLUG = "web_fetch";
const NEW_DESCRIPTION = "LE2272 distinctive description";

// LE-2272: the tool actions editor applies its edits to the node only on close.
// A custom_component/update response issued before those edits but landing after
// them used to be applied wholesale, reverting the slug, the description and
// approval_actions — and the autosave then persisted the loss.
test(
  "tool action edits survive a custom_component/update response that lands late",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("url");
    await page.waitForSelector('[data-testid="data_sourceURL"]', {
      timeout: 30000,
    });
    await page.getByTestId("data_sourceURL").hover();
    await page.getByTestId("add-component-button-url").click();
    await adjustScreenView(page);

    // Hold the pre-edit tools_metadata refresh and release it only once the
    // editor has closed, so its response is stale by the time it is applied.
    let alreadyHeld = false;
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route("**/api/v1/custom_component/update", async (route) => {
      const body = route.request().postData() ?? "";
      if (!alreadyHeld && body.includes('"field":"tools_metadata"')) {
        alreadyHeld = true;
        await gate;
      }
      await route.continue();
    });

    await page.getByTestId("title-URL").first().click();
    await page.keyboard.press("ControlOrMeta+Shift+m");
    await page.waitForSelector('[data-testid="button_open_actions"]', {
      timeout: 30000,
    });

    await page.getByTestId("button_open_actions").click();
    await expect(page.getByText("FETCH_CONTENT").first()).toBeVisible({
      timeout: 30000,
    });

    await page
      .locator('.ag-center-cols-container .ag-row [col-id="description"]')
      .first()
      .click({ force: true });
    await expect(page.getByTestId("input_update_name")).toBeVisible({
      timeout: 30000,
    });

    await page.getByTestId("input_update_name").fill(NEW_SLUG);
    await page.getByTestId("input_update_description").fill(NEW_DESCRIPTION);

    // The row refreshes as the edits above land, which can recreate the
    // switch cell out from under a click; retry until the toggle takes.
    const toggle = page.getByTestId("requires-approval-toggle").first();
    await expect(async () => {
      if ((await toggle.getAttribute("aria-checked")) !== "true") {
        await toggle.click();
      }
      await expect(toggle).toHaveAttribute("aria-checked", "true", {
        timeout: 1000,
      });
    }).toPass({ timeout: 30000 });
    // The switch renders instantly but persists onto the row after its slide
    // transition, so give that timer room before closing the editor.
    await page.waitForTimeout(600);
    await expect(toggle).toHaveAttribute("aria-checked", "true");

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("input_update_name")).toBeHidden({
      timeout: 30000,
    });

    release();
    await page.waitForTimeout(4000);

    await page.getByTestId("button_open_actions").click();
    await expect(page.getByText("WEB_FETCH").first()).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByText(NEW_DESCRIPTION).first()).toBeVisible({
      timeout: 30000,
    });
    await expect(
      page.getByTestId("requires-approval-toggle").first(),
    ).toHaveAttribute("aria-checked", "true");
    await page.keyboard.press("Escape");

    // The reverted node used to reach the database through the debounced autosave.
    const flowId = page.url().split("/flow/")[1]?.split("/")[0];
    await expect
      .poll(
        async () => {
          const response = await page.request.get(
            `http://localhost:7860/api/v1/flows/${flowId}`,
          );
          const flow = await response.json();
          const node = flow?.data?.nodes?.find((candidate) =>
            candidate?.id?.toLowerCase().includes("url"),
          );
          return node?.data?.node?.template?.tools_metadata?.value?.[0] ?? null;
        },
        { timeout: 30000 },
      )
      .toMatchObject({
        name: NEW_SLUG,
        description: NEW_DESCRIPTION,
        approval_actions: ["approve", "reject"],
      });
  },
);
