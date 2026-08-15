import { expect, type LangflowPage, test } from "../fixtures";
import { adjustScreenView } from "../utils/adjust-screen-view";
import { TID } from "../utils/constants/testIds";
import { TEXTS } from "../utils/constants/texts";
import { TIMEOUTS } from "../utils/constants/timeouts";
import { addComponentFromSidebar } from "../utils/flow/add-component-from-sidebar";
import { openBlankFlow } from "../utils/flow/open-blank-flow";

// Covers `/playground/:id/` (PlaygroundAuthGate -> PlaygroundPage), the
// standalone shared playground. Unlike the in-editor playground modal, this
// route renders CustomIOModal as the *entire page* with no app header, no
// sidebar and no landmark chrome around it, so its accessibility profile is
// distinct from the `playground-*` states scanned in core-pages.a11y.spec.ts.
//
// PlaygroundPage refuses to render unless the flow's `access_type` is PUBLIC
// and the flow has at least one input or output — otherwise it navigates to
// "/". The setup below therefore builds a Chat Input -> Chat Output flow and
// flips the publish switch, which needs no external API key.

// How many Tab presses forward of the chat input the send button is allowed to
// be. Today it is 2 (an "Attach file" button sits between them); the slack
// absorbs future composer controls without silently accepting a send button
// that has fallen out of the composer's tab ring entirely.
const COMPOSER_TAB_BUDGET = 5;

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

async function forceDarkTheme(page: LangflowPage) {
  await page.addInitScript(() => {
    window.localStorage.setItem("themePreference", "dark");
    window.localStorage.setItem("isDark", "true");
  });
}

/**
 * Build a minimal chat flow, publish it, and return its id so the caller can
 * navigate to the standalone `/playground/:id/` surface.
 */
async function publishChatFlowAndGetId(page: LangflowPage): Promise<string> {
  await openBlankFlow(page);
  await expect(page.getByTestId(TID.sidebarSearchInput)).toBeVisible({
    timeout: TIMEOUTS.standard,
  });

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
  await page
    .getByTestId("handle-chatinput-noshownode-chat message-source")
    .click();
  await page.getByTestId("handle-chatoutput-noshownode-inputs-target").click();
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);

  const flowId = new URL(page.url()).pathname.match(/\/flow\/([^/?#]+)/)?.[1];
  if (!flowId) {
    throw new Error(`Expected a /flow/:id editor URL, got ${page.url()}`);
  }

  // Persist the graph before publishing. In auto-save-off configurations the
  // save button owns this request; with auto-save enabled it may already be
  // disabled because the same graph has reached the backend.
  const saveButton = page.getByTestId("save-flow-button");
  if ((await saveButton.count()) > 0) {
    await expect(saveButton).toBeEnabled({ timeout: TIMEOUTS.medium });
    const saveResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        response.request().method() === "PATCH" &&
        url.pathname === `/api/v1/flows/${flowId}`
      );
    });
    await saveButton.click();
    const saveResponse = await saveResponsePromise;
    expect(
      saveResponse.ok(),
      `Saving flow ${flowId} returned ${saveResponse.status()}`,
    ).toBeTruthy();
  }

  await expect
    .poll(
      async () => {
        const response = await page.request.get(`/api/v1/flows/${flowId}`);
        if (!response.ok()) {
          return { status: response.status(), nodes: 0, edges: 0 };
        }
        const flow = (await response.json()) as {
          data?: { nodes?: unknown[]; edges?: unknown[] };
        };
        return {
          status: response.status(),
          nodes: flow.data?.nodes?.length ?? 0,
          edges: flow.data?.edges?.length ?? 0,
        };
      },
      { message: `Flow ${flowId} graph was not persisted before publish` },
    )
    .toEqual({ status: 200, nodes: 2, edges: 1 });

  await page.getByTestId(TID.publishButton).click();
  await expect(page.getByTestId(TID.publishSwitch)).toBeVisible({
    timeout: TIMEOUTS.medium,
  });
  const publishResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "PATCH" &&
      url.pathname === `/api/v1/flows/${flowId}`
    );
  });
  await page.getByTestId(TID.publishSwitch).click();
  const publishResponse = await publishResponsePromise;
  expect(
    publishResponse.ok(),
    `Publishing flow ${flowId} returned ${publishResponse.status()}`,
  ).toBeTruthy();
  await expect(page.getByTestId(TID.publishSwitch)).toBeChecked({
    timeout: TIMEOUTS.medium,
  });

  return flowId;
}

async function openSharedPlayground(page: LangflowPage, flowId: string) {
  // The disableAnimations style tag only freezes CSS animations; framer-motion
  // animates inline styles from JS. TextEffect renders statically under
  // prefers-reduced-motion, but framer's useReducedMotion reads the preference
  // once at mount, so emulate it *before* navigating — otherwise the empty-state
  // text is scanned mid-fade with low-contrast intermediate frames.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/playground/${flowId}/`);
  // A non-public flow bounces to "/", so still being on /playground/ once the
  // chat input mounts is itself the assertion that the surface loaded.
  await expect(page.getByTestId(TID.inputChatPlayground)).toBeVisible({
    timeout: TIMEOUTS.long,
  });
  await expect(page).toHaveURL(new RegExp(`/playground/${flowId}/?$`));
  await disableAnimations(page);
}

async function collectTabStops(page: LangflowPage, steps: number) {
  await page.evaluate(() => {
    (document.activeElement as HTMLElement | null)?.blur();
    document.body.focus();
  });

  const stops: Array<{ tag: string; testId: string; label: string }> = [];
  for (let i = 0; i < steps; i++) {
    await page.keyboard.press("Tab");
    stops.push(
      await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        return {
          tag: el?.tagName ?? "NONE",
          testId: el?.getAttribute("data-testid") ?? "",
          label:
            el?.getAttribute("aria-label") ??
            el?.getAttribute("placeholder") ??
            (el?.textContent ?? "").trim().slice(0, 40),
        };
      }),
    );
  }
  return stops;
}

test.describe("shared playground accessibility", () => {
  test.describe.configure({ mode: "serial" });

  test(
    "scans the standalone shared playground in light and dark mode",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      const flowId = await publishChatFlowAndGetId(page);
      await openSharedPlayground(page, flowId);

      // WCAG 2.4.2: PlaygroundPage sets document.title from the flow name; an
      // empty title leaves shared links unidentifiable in tabs and history.
      await expect
        .poll(() => page.title(), { timeout: TIMEOUTS.medium })
        .not.toBe("");

      await page.runA11yScan("shared-playground-empty");

      await forceDarkTheme(page);
      await page.reload();
      await expect(page.locator("body")).toHaveClass(/dark/);
      await expect(page.getByTestId(TID.inputChatPlayground)).toBeVisible({
        timeout: TIMEOUTS.long,
      });
      await disableAnimations(page);

      await page.runA11yScan("shared-playground-empty-dark", {
        colorScheme: "dark",
      });
    },
  );

  test(
    "scans the shared playground with a chat transcript",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      const flowId = await publishChatFlowAndGetId(page);
      await openSharedPlayground(page, flowId);

      await page
        .getByTestId(TID.inputChatPlayground)
        .fill("Accessibility test");
      await page.getByTestId(TID.buttonSend).last().click();
      await expect(page.getByTestId(TID.chatMessage).first()).toHaveText(
        "Accessibility test",
        { timeout: TIMEOUTS.componentMount },
      );

      await page.runA11yScan("shared-playground-with-message");
    },
  );

  test(
    "keyboard users can reach the message input and send button",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      const flowId = await publishChatFlowAndGetId(page);
      await openSharedPlayground(page, flowId);

      // WCAG 2.1.1 / 2.4.3: the chat composer is the only way to use a shared
      // playground, so it must be reachable by tabbing rather than by pointer.
      const stops = await collectTabStops(page, 20);
      const reachedInput = stops.some(
        (stop) =>
          stop.testId === TID.inputChatPlayground ||
          stop.label === TEXTS.placeholderSendMessage,
      );
      expect(
        reachedInput,
        `Tab never reached the chat input. Stops: ${JSON.stringify(stops)}`,
      ).toBe(true);

      // The send control must also be a real tab stop, not a click-only icon.
      // It is *not* adjacent to the textarea: the real composer order is
      // textarea -> "Attach file (...)" button -> send button, so walk a few
      // stops forward rather than assuming adjacency. Send is only enabled once
      // the composer has content, hence the fill first.
      await page.getByTestId(TID.inputChatPlayground).fill("Keyboard check");
      await page.getByTestId(TID.inputChatPlayground).focus();

      const composerStops: Array<{
        testId: string;
        name: string;
        disabled: boolean;
      }> = [];
      for (let i = 0; i < COMPOSER_TAB_BUDGET; i++) {
        await page.keyboard.press("Tab");
        composerStops.push(
          await page.evaluate(() => {
            const el = document.activeElement as HTMLElement | null;
            return {
              testId: el?.getAttribute("data-testid") ?? "",
              name:
                el?.getAttribute("aria-label") ??
                (el?.textContent ?? "").trim().slice(0, 60),
              disabled: el?.hasAttribute("disabled") ?? true,
            };
          }),
        );
        if (composerStops.at(-1)?.testId === TID.buttonSend) break;
      }

      const sendStop = composerStops.find(
        (stop) => stop.testId === TID.buttonSend,
      );
      expect(
        sendStop,
        `Send button was not reachable within ${COMPOSER_TAB_BUDGET} tabs of the chat input. Stops: ${JSON.stringify(composerStops)}`,
      ).toBeDefined();
      expect(
        sendStop?.disabled,
        `Send button is a tab stop but is disabled with text in the composer. Stops: ${JSON.stringify(composerStops)}`,
      ).toBe(false);

      // WCAG 4.1.2: every control a keyboard user is forced through on the way
      // to Send must expose an accessible name, or the ordering above is just
      // a sequence of unlabelled stops to a screen reader.
      for (const stop of composerStops) {
        expect(
          stop.name,
          `Composer tab stop has no accessible name: ${JSON.stringify(stop)}`,
        ).not.toBe("");
      }
    },
  );

  test(
    "shared playground does not trap keyboard focus",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      const flowId = await publishChatFlowAndGetId(page);
      await openSharedPlayground(page, flowId);

      // WCAG 2.1.2: the playground renders as a full-screen modal shell. Focus
      // may legitimately cycle within it, but it must not stick to one element.
      const stops = await collectTabStops(page, 20);
      const distinct = new Set(
        stops.map((stop) => `${stop.tag}:${stop.testId}:${stop.label}`),
      );
      expect(
        distinct.size,
        `Focus appears trapped. Stops: ${JSON.stringify(stops)}`,
      ).toBeGreaterThan(1);
    },
  );
});
