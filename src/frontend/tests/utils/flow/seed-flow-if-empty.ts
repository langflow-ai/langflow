import { expect, type Page, type Response } from "@playwright/test";
import { TID } from "../constants/testIds";
import { TEXTS } from "../constants/texts";
import { TIMEOUTS } from "../constants/timeouts";
import { openTemplatesModal } from "./new-project-flow";
import { selectStarterTemplate } from "./select-starter-template";
import { waitForFlowEditorReady } from "./wait-for-flow-editor-ready";

const SEEDED_FLOW_NAME = TEXTS.templateBasicPrompting;
// Playwright's default desktop viewport. Seeding drives the desktop flow
// editor (templates modal -> component sidebar), which is unreachable at
// mobile widths.
const SEED_VIEWPORT = { width: 1280, height: 720 };

function isFlowCreateResponse(response: Response): boolean {
  return (
    response.request().method() === "POST" &&
    new URL(response.url()).pathname === "/api/v1/flows/"
  );
}

async function isExactNameUniquenessRace(
  response: Response | undefined,
): Promise<boolean> {
  if (!response || response.status() !== 400) {
    return false;
  }

  const body = await response.json().catch(() => null);
  return (
    body !== null &&
    typeof body === "object" &&
    !Array.isArray(body) &&
    Object.keys(body).length === 1 &&
    (body as { detail?: unknown }).detail === "Name must be unique"
  );
}

async function waitForConcurrentSeed(page: Page): Promise<void> {
  await expect
    .poll(
      async () => {
        const response = await page.request.get(
          "/api/v1/flows/?get_all=true&header_flows=true&remove_example_flows=true",
        );
        if (!response.ok()) {
          throw new Error(
            `Reading flows after a concurrent seed returned ${response.status()}`,
          );
        }

        const flows = await response.json();
        if (!Array.isArray(flows)) {
          throw new Error(
            "Reading flows after a concurrent seed returned malformed data",
          );
        }
        return flows.some(
          (flow) =>
            flow !== null &&
            typeof flow === "object" &&
            (flow as { name?: unknown }).name === SEEDED_FLOW_NAME,
        );
      },
      {
        message: `A concurrent seed won the name race but ${SEEDED_FLOW_NAME} never appeared`,
        timeout: TIMEOUTS.standard,
      },
    )
    .toBe(true);

  await page.goto("/");
  await expect(page.getByTestId(TID.mainpageTitle)).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
  await expect(page.getByTestId(TID.newProjectBtn)).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
  await expect(
    page
      .getByTestId("flow-name-div")
      .filter({ hasText: SEEDED_FLOW_NAME })
      .first(),
  ).toBeVisible({ timeout: TIMEOUTS.standard });
}

export async function seedFlowIfEmpty(page: Page): Promise<boolean> {
  const emptyPageButton = page.getByTestId(TID.newProjectBtnEmptyPage);
  const regularNewProjectButton = page.getByTestId(TID.newProjectBtn);
  await expect
    .poll(
      async () =>
        (await emptyPageButton.isVisible().catch(() => false)) ||
        (await regularNewProjectButton.isVisible().catch(() => false)),
      { timeout: TIMEOUTS.standard },
    )
    .toBe(true);

  if (!(await emptyPageButton.isVisible())) {
    return false;
  }

  let latestCreateResponse: Response | undefined;
  const rememberCreateResponse = (response: Response) => {
    if (isFlowCreateResponse(response)) {
      latestCreateResponse = response;
    }
  };
  page.on("response", rememberCreateResponse);
  let placeholderFlowId: string | undefined;

  // A mobile-viewport test can be the first to hit an empty workspace (each CI
  // shard starts from a fresh DB), so seed at desktop width and restore the
  // test's viewport afterwards.
  const testViewport = page.viewportSize();
  const widenForSeed =
    testViewport !== null && testViewport.width < SEED_VIEWPORT.width;

  try {
    if (widenForSeed) {
      await page.setViewportSize(SEED_VIEWPORT);
    }
    await openTemplatesModal(page, { fromEmptyPage: true });
    placeholderFlowId = new URL(page.url()).pathname.match(
      /\/flow\/([^/?#]+)/,
    )?.[1];
    expect(
      placeholderFlowId,
      "Empty-state seeding must create a blank placeholder flow",
    ).toBeTruthy();
    await selectStarterTemplate(page, SEEDED_FLOW_NAME);
    await waitForFlowEditorReady(page);
    await page.goto("/");
    await expect(page.getByTestId(TID.mainpageTitle)).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
  } catch (error) {
    // Parallel workers can both observe the empty state and choose the same
    // fixed seed name. Only the exact backend uniqueness response proves that
    // another worker won that race; every other 4xx and every 5xx remains a
    // hard failure.
    const exactNameRace = await isExactNameUniquenessRace(latestCreateResponse);
    if (!exactNameRace) {
      throw error;
    }

    // A conflict from the initial blank-flow POST means this worker never
    // created anything. A conflict after opening the templates modal means it
    // owns a blank placeholder that the normal flow-switch cleanup never sees,
    // so delete only that known id before returning home.
    if (placeholderFlowId) {
      const cleanupResponse = await page.request.delete("/api/v1/flows/", {
        data: [placeholderFlowId],
      });
      expect(
        cleanupResponse.ok(),
        `Deleting the losing seed placeholder returned ${cleanupResponse.status()}`,
      ).toBeTruthy();
      await cleanupResponse.body();
    }

    await waitForConcurrentSeed(page);
  } finally {
    page.off("response", rememberCreateResponse);
    if (widenForSeed && testViewport) {
      await page.setViewportSize(testViewport);
    }
  }

  return true;
}
