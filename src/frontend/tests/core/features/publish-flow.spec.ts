import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TID } from "../../utils/constants/testIds";
import { TEXTS } from "../../utils/constants/texts";
import { ANIMATIONS, TIMEOUTS } from "../../utils/constants/timeouts";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";

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

    // Wait for the chat input to actually be present before filling. The
    // default actionTimeout (20s) was not enough on Windows CI for the
    // shareable-playground page to mount the message input.
    await newPage
      .getByPlaceholder(TEXTS.placeholderSendMessage)
      .waitFor({ state: "visible", timeout: TIMEOUTS.long });
    const newUrl = newPage.url();
    await newPage.getByPlaceholder(TEXTS.placeholderSendMessage).fill("Hello");
    await newPage.getByTestId(TID.buttonSend).last().click();

    const stopButton = newPage.getByRole("button", { name: TEXTS.stop });
    await stopButton.waitFor({ state: "visible", timeout: TIMEOUTS.standard });

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
