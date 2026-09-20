import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

const NEW_ACTION = "Request Changes";

// LE-2278: Human Input fires an on-mount decisions refresh. Its response was
// applied over a User Action added while it was still in flight, so the chip
// vanished, the node kept the orphan branch output, and the autosave persisted
// the reverted value. Same family as LE-2272.
test(
  "a custom User Action survives a decisions refresh response that lands late",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("human input");
    await page.waitForSelector('[data-testid="flow_controlsHuman Input"]', {
      timeout: 30000,
    });

    // Hold the on-mount decisions refresh. Its round trip runs now and only the
    // delivery waits, so releasing it lands the response immediately - the
    // window between the user's commit and the field-change request leaving.
    let alreadyHeld = false;
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route("**/api/v1/custom_component/update", async (route) => {
      const body = route.request().postData() ?? "";
      if (!alreadyHeld && body.includes('"field":"decisions"')) {
        alreadyHeld = true;
        const response = await route.fetch();
        await gate;
        await route.fulfill({ response });
        return;
      }
      await route.continue();
    });

    await page.getByTestId("flow_controlsHuman Input").hover();
    await page.getByTestId("add-component-button-human-input").click();
    await adjustScreenView(page);

    await page.getByTestId("actionpicker-add-decisions").click();
    await page.getByTestId("action-add-input").fill(NEW_ACTION);
    await page.keyboard.press("Enter");
    await expect(page.getByTestId(`action-edit-${NEW_ACTION}`)).toBeVisible({
      timeout: 30000,
    });

    release();

    await expect(page.getByTestId(`action-edit-${NEW_ACTION}`)).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByTestId("action-edit-Approve")).toBeVisible();
    await expect(page.getByTestId("action-edit-Reject")).toBeVisible();

    // The reverted value used to reach the database, leaving chips and branch
    // outputs inconsistent there too.
    const flowId = page.url().split("/flow/")[1]?.split("/")[0];
    await expect
      .poll(
        async () => {
          const response = await page.request.get(
            `http://localhost:7860/api/v1/flows/${flowId}`,
          );
          const flow = await response.json();
          const node = flow?.data?.nodes?.find((candidate) =>
            candidate?.id?.toLowerCase().includes("humaninput"),
          );
          if (!node) return null;
          return {
            decisions: node.data?.node?.template?.decisions?.value ?? null,
            outputs: (node.data?.node?.outputs ?? []).map((o) => o.name),
          };
        },
        { timeout: 30000 },
      )
      .toEqual({
        decisions: ["Approve", "Reject", NEW_ACTION],
        outputs: ["branch_approve", "branch_reject", "branch_request_changes"],
      });
  },
);
