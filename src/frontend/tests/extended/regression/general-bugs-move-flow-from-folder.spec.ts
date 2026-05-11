import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { renameFlow } from "../../utils/rename-flow";

test("user must be able to move flow from folder", async ({ page }) => {
  /* This is the original, happy-path regression: the destination
   * project is BRAND NEW and has never been observed by React Query,
   * so its `useGetFolder` cache doesn't exist and the first visit
   * after the drop triggers a fresh fetch. It exercises drag-and-drop
   * plumbing but does not exercise stale cache invalidation. */
  const randomName = Math.random().toString(36).substring(2, 15);

  await awaitBootstrapTest(page);

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForTimeout(2000);

  await renameFlow(page, { flowName: randomName });

  await page.waitForTimeout(2000);

  await page.getByTestId("icon-ChevronLeft").click();
  await page.waitForSelector('[data-testid="add-project-button"]', {
    timeout: 3000,
  });

  await page.getByTestId("add-project-button").click();

  //wait for the project to be created and changed to the new project
  await page.waitForTimeout(2000);

  await page.getByTestId("sidebar-nav-Starter Project").click();

  await page.waitForTimeout(2000);

  await page.getByText(randomName).hover();

  await page
    .getByTestId("list-card")
    .first()
    .dragTo(page.locator('//*[@id="sidebar-nav-New Project"]'));

  //wait for the drag and drop to be completed
  await page.waitForTimeout(2000);

  await page.getByTestId("sidebar-nav-New Project").click();

  await page.waitForSelector('[data-testid="list-card"]');

  const flowNameCount = await page.getByText(randomName).count();
  expect(flowNameCount).toBeGreaterThan(0);
});

test("moved flow must appear when destination project was visited while still empty", async ({
  page,
}) => {
  /* Reproduces the real bug scenario:
   *
   *  1. Create an empty destination project and OBSERVE it (visit it
   *     once while still empty). This populates the `useGetFolder`
   *     cache with `total: 0`.
   *  2. Navigate away to the source project.
   *  3. Drag a flow from the source to the now-stale destination.
   *  4. Click the destination and verify the moved flow appears.
   *
   * Before the `usePatchUpdateFlow` invalidation fix + `isEmptyFolder`
   * dual-source fix, the destination kept showing the "Empty project"
   * / "flows not supported" state until a manual page refresh, because
   * BOTH the folder query cache and the global flows store were
   * stale and nothing re-triggered them. */
  const flowName = `stale-${Math.random().toString(36).substring(2, 10)}`;

  await awaitBootstrapTest(page);

  // Create a flow and rename it so we can find it later by a unique name.
  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();
  await page.waitForTimeout(2000);
  await renameFlow(page, { flowName });
  await page.waitForTimeout(2000);
  await page.getByTestId("icon-ChevronLeft").click();

  // Step 1: create a destination project. `add-project-button`
  // navigates the UI INTO the new project automatically — we rely on
  // that because it populates the React Query cache with the empty
  // folder state (`total: 0`), which is exactly what we want to
  // defeat.
  await page.waitForSelector('[data-testid="add-project-button"]', {
    timeout: 5000,
  });
  await page.getByTestId("add-project-button").click();

  // Confirm we landed on the new (empty) project and the empty-state
  // UI rendered — this guarantees `useGetFolder` has actually fired
  // and cached `total: 0` for the destination.
  await expect(page.getByTestId("sidebar-nav-New Project")).toBeVisible({
    timeout: 10000,
  });
  await page.waitForTimeout(1000);

  // Step 2: go back to the source project. The destination's query
  // becomes inactive but stays in the cache with the stale empty
  // payload.
  await page.getByTestId("sidebar-nav-Starter Project").click();
  await expect(page.getByText(flowName).first()).toBeVisible({
    timeout: 10000,
  });

  // Step 3: real HTML5 drag-and-drop — `dragTo()` populates
  // `DataTransfer` so `use-on-file-drop.ts` actually triggers
  // `saveFlow`. `page.mouse.down/up` would NOT.
  await page
    .getByTestId("list-card")
    .filter({ hasText: flowName })
    .first()
    .dragTo(page.getByTestId("sidebar-nav-New Project"));

  // Give the PATCH request time to complete but NOT enough time for a
  // full page refresh to matter. If the fix works, the query cache
  // and the global store will both be refreshed by the mutation's
  // invalidation, and the empty state will never render.
  await page.waitForTimeout(500);

  // Step 4: click the destination. The flow must be visible. Use a
  // short polling timeout — a long `waitForSelector` would mask the
  // bug by giving React Query's implicit `refetchOnMount` enough
  // runway to recover behind the scenes.
  await page.getByTestId("sidebar-nav-New Project").click();

  await expect(
    page.getByTestId("list-card").filter({ hasText: flowName }).first(),
  ).toBeVisible({ timeout: 3000 });

  // And the empty-state placeholder must NOT be rendered.
  await expect(page.getByText("Begin with a template")).toHaveCount(0);
});
