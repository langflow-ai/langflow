import type { Route } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { openStarterProject } from "../../utils/flow/open-starter-project";

type ModelValue = Array<{ name: string; provider: string }>;

const isMountRefresh = (route: Route): boolean => {
  try {
    return route.request().postDataJSON()?.template?.is_refresh === true;
  } catch {
    return false;
  }
};

test(
  "keeps a model picked while the flow-open model refresh is in flight",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to list more than one selectable model",
    );

    let releaseRefresh: () => void = () => {};
    const refreshReleased = new Promise<void>((resolve) => {
      releaseRefresh = resolve;
    });
    let heldRefreshes = 0;
    await page.route("**/api/v1/custom_component/update**", async (route) => {
      if (!isMountRefresh(route)) {
        await route.continue();
        return;
      }
      heldRefreshes += 1;
      const response = await route.fetch();
      await refreshReleased;
      await route.fulfill({ response });
    });

    await openStarterProject(page, "Basic Prompting");
    await expect.poll(() => heldRefreshes).toBeGreaterThan(0);

    const trigger = page.getByTestId("model_model").first();
    await expect(trigger).toBeVisible({ timeout: 30000 });
    const initialModel = (await trigger.innerText()).trim();
    await trigger.click();

    const alternative = page
      .locator('[cmdk-item][data-testid$="-option"]')
      .filter({ hasNotText: initialModel })
      .last();
    await expect(alternative).toBeVisible({ timeout: 30000 });
    const pickedModel = (await alternative.innerText()).split("\n")[0].trim();
    const pickUpdated = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/custom_component/update") &&
        JSON.stringify(
          response.request().postDataJSON()?.field_value ?? "",
        ).includes(pickedModel),
    );
    await alternative.click();
    await expect(trigger).toContainText(pickedModel);
    await pickUpdated;

    const refreshApplied = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/custom_component/update") &&
        response.request().postDataJSON()?.template?.is_refresh === true,
    );
    releaseRefresh();
    await refreshApplied;
    // The app applies the response after the network event; let it land first.
    await page.waitForTimeout(2000);

    await expect(trigger).toContainText(pickedModel);
    const flowId = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/)?.[1];
    await expect
      .poll(
        async () => {
          const flow = await (
            await page.request.get(`/api/v1/flows/${flowId}`)
          ).json();
          const modelNode = flow.data?.nodes?.find(
            (node: { data: { node: { template: { model?: unknown } } } }) =>
              node.data.node.template.model,
          );
          const value = modelNode?.data.node.template.model.value as ModelValue;
          return value?.[0]?.name;
        },
        { timeout: 15000 },
      )
      .toBe(pickedModel);
  },
);
