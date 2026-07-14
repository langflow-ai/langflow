import { expect, type LangflowPage, test } from "../fixtures";
import { adjustScreenView } from "../utils/adjust-screen-view";
import { TID } from "../utils/constants/testIds";
import { TEXTS } from "../utils/constants/texts";
import { TIMEOUTS } from "../utils/constants/timeouts";
import { addComponentFromSidebar } from "../utils/flow/add-component-from-sidebar";

async function disableAnimations(page: LangflowPage) {
  await page.addStyleTag({
    content: `
      *,
      *::before,
      *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
        scroll-behavior: auto !important;
      }
    `,
  });
}

async function hideComponentSidebar(page: LangflowPage) {
  const style = await page.addStyleTag({
    content: '[data-testid="shad-sidebar"] { display: none !important; }',
  });
  await expect(page.getByTestId("shad-sidebar")).toBeHidden();
  return style;
}

async function openBlankFlowForA11y(page: LangflowPage) {
  await page.goto("/");
  await expect(page.getByTestId(TID.mainpageTitle)).toBeVisible({
    timeout: TIMEOUTS.standard,
  });

  const emptyPageButton = page.getByTestId(TID.newProjectBtnEmptyPage);
  if (await emptyPageButton.isVisible()) {
    await emptyPageButton.click();
  } else {
    await page.getByTestId(TID.newProjectBtn).click();
  }

  const welcomePanel = page.getByTestId("flow-builder-welcome-panel");
  const modalTitle = page.getByTestId(TID.modalTitle);
  await expect(welcomePanel.or(modalTitle)).toBeVisible({
    timeout: TIMEOUTS.standard,
  });

  if (await welcomePanel.isVisible()) {
    await page.getByTestId("flow-builder-welcome-browse-more").click();
  }

  await expect(page.getByTestId(TID.blankFlow)).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
  await page.getByTestId(TID.blankFlow).click();
}

test.describe("core application accessibility", () => {
  test.describe.configure({ mode: "serial" });

  test(
    "scans flow creation and playground states",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openBlankFlowForA11y(page);
      await disableAnimations(page);
      await expect(page.getByTestId(TID.sidebarSearchInput)).toBeVisible();
      const emptyCanvasSidebarStyle = await hideComponentSidebar(page);

      await page.runA11yScan("flow-canvas-empty");

      await emptyCanvasSidebarStyle.evaluate((style) => style.remove());
      await expect(page.getByTestId(TID.sidebarSearchInput)).toBeVisible();
      await addComponentFromSidebar(page, {
        search: TEXTS.searchChatOutput,
        testId: "input_outputChat Output",
        hoverAdd: true,
      });
      await addComponentFromSidebar(page, {
        search: TEXTS.searchChatInput,
        testId: "input_outputChat Input",
        position: { x: 100, y: 100 },
      });
      await adjustScreenView(page);
      await hideComponentSidebar(page);

      await page
        .getByTestId("handle-chatinput-noshownode-chat message-source")
        .click();
      await page
        .getByTestId("handle-chatoutput-noshownode-inputs-target")
        .click();

      await page.runA11yScan("flow-canvas-populated");

      await page.getByTestId("title-Chat Input").click();
      await expect(page.getByTestId(TID.parametersButton)).toBeVisible();
      await page.getByTestId(TID.parametersButton).click();
      await expect(
        page.getByTestId("inspector-param-input_value"),
      ).toBeVisible();

      await page.runA11yScan("component-configuration");

      await page.getByTestId("inspection-panel-close").click();
      await page
        .getByRole("button", { name: TEXTS.playground, exact: true })
        .click();
      await expect(page.getByTestId(TID.inputChatPlayground)).toBeVisible({
        timeout: TIMEOUTS.componentMount,
      });

      await page.runA11yScan("playground-empty");

      await page
        .getByTestId(TID.inputChatPlayground)
        .fill("Accessibility test");
      await page.getByTestId(TID.buttonSend).first().click();
      await expect(page.getByTestId(TID.chatMessage)).toHaveText(
        "Accessibility test",
        { timeout: TIMEOUTS.componentMount },
      );

      await page.runA11yScan("playground-with-message");
    },
  );
});
