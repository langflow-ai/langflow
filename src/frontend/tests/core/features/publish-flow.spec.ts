import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TID } from "../../utils/constants/testIds";
import { ANIMATIONS, TIMEOUTS } from "../../utils/constants/timeouts";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import { sendPlaygroundMessage } from "../../utils/playground/send-playground-message";

test(
  "user should be able to publish a flow",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page, context }) => {
    await openBlankFlow(page);
    await page.waitForSelector(`[data-testid="${TID.sidebarSearchInput}"]`, {
      timeout: TIMEOUTS.short,
    });

    await addComponentFromSidebar(page, {
      search: "chat input",
      testId: "input_outputChat Input",
      hoverAdd: true,
    });

    await adjustScreenView(page, { numberOfZoomOut: 3 });
    await page.getByTestId(TID.publishButton).click();

    await page.waitForSelector(`[data-testid="${TID.shareablePlayground}"]`, {
      timeout: TIMEOUTS.medium,
    });

    await expect(page.getByTestId(TID.publishSwitch)).toBeVisible({
      timeout: TIMEOUTS.medium,
    });

    await page.getByTestId(TID.publishSwitch).click();
    const pagePromise = context.waitForEvent("page");
    await page.waitForTimeout(ANIMATIONS.publishTogglePropagation);

    await page.getByTestId(TID.shareablePlayground).click();
    const newPage = await pagePromise;
    await newPage.waitForLoadState("domcontentloaded");

    // Run the published flow to completion before leaving the page. The
    // helper waits for the chat input (slow to mount on Windows CI), sends,
    // and only returns once the Stop button has cleared. Closing the tab while
    // the build was still in flight aborted the backend request mid-write; on
    // SQLite that cancellation can leave a write transaction open until GC and
    // stall every other writer, which is how the un-publish PATCH below hung
    // for 10s+ (nightly 31907290063, shard 41). Waiting also proves the
    // shareable playground actually completes a run.
    await sendPlaygroundMessage(newPage, "Hello", { surface: "shareable" });
    const newUrl = newPage.url();

    await newPage.close();
    await page.bringToFront();
    await page.getByTestId(TID.publishButton).click();
    await page.getByTestId(TID.publishSwitch).click();
    await expect(page.getByTestId("rf__wrapper")).toBeVisible();
    await expect(page.getByTestId(TID.publishSwitch)).toBeChecked({
      checked: false,
    });
    await expect(page.getByTestId("rf__wrapper")).toBeVisible();

    // The publish-switch toggle is confirmed in the UI above, but the
    // un-publish has to reach the backend before the shareable URL stops
    // resolving — give it time to propagate.
    await page.waitForTimeout(ANIMATIONS.publishTogglePropagation);

    await page.goto(newUrl);

    // An un-published playground URL redirects to the projects page:
    // PlaygroundPage detects access_type !== "PUBLIC" and navigates to
    // "/". The redirect is client-side and the subsequent app bootstrap
    // can be slow on CI, so wait for the URL to leave /playground/
    // before asserting the projects page rendered.
    await page.waitForURL((url) => !url.pathname.startsWith("/playground/"), {
      timeout: TIMEOUTS.long,
    });
    await expect(page.getByTestId(TID.mainpageTitle)).toBeVisible({
      timeout: TIMEOUTS.long,
    });
  },
);
