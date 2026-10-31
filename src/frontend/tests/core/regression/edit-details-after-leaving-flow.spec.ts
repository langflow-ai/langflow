import { expect, test } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { openStarterProject } from "../../utils/flow/open-starter-project";

test(
  "should save Edit details from the home page after leaving a flow in-app",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openStarterProject(page, TEXTS.templateBasicPrompting);
    const flowId = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/)?.[1];
    if (!flowId) throw new Error(`Expected a flow URL; got ${page.url()}`);

    // In-app navigation keeps the editor's store state; page.goto would reload
    // and hide a save bound to the unmounted editor.
    await page.getByTestId("icon-ChevronLeft").first().click();
    await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
      timeout: 30000,
    });

    const newName = `renamed-${Math.random().toString(36).substring(2, 10)}`;
    const card = page
      .getByTestId("list-card")
      .filter({ has: page.getByTestId(`checkbox-${flowId}`) });
    await card.getByTestId("home-dropdown-menu").click();
    await page.getByTestId("btn-edit-flow").click();
    await page.getByTestId("input-flow-name").fill(newName);

    const patchDone = page.waitForResponse(
      (response) =>
        response.request().method() === "PATCH" &&
        new URL(response.url()).pathname === `/api/v1/flows/${flowId}`,
    );
    await page.getByTestId("save-flow-settings").click();
    expect((await patchDone).ok()).toBe(true);

    await expect(page.getByTestId("save-flow-settings")).toBeHidden({
      timeout: 10000,
    });
    await expect(page.getByText(newName).first()).toBeVisible();
    const persisted = await page.request.get(`/api/v1/flows/${flowId}`);
    expect(((await persisted.json()) as { name: string }).name).toBe(newName);
  },
);
