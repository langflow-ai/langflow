import {
  expect,
  type Page,
  type Request,
  type Response,
} from "@playwright/test";
import { TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";

function requestDeletesFlow(request: Request, flowId: string): boolean {
  if (
    request.method() !== "DELETE" ||
    new URL(request.url()).pathname !== "/api/v1/flows/"
  ) {
    return false;
  }

  try {
    const body = request.postDataJSON();
    return Array.isArray(body) && body.includes(flowId);
  } catch {
    return false;
  }
}

async function assertResponseFinished(
  response: Response,
  description: string,
): Promise<void> {
  expect(
    response.ok(),
    `${description} returned ${response.status()} ${response.statusText()}`,
  ).toBeTruthy();
  expect(await response.finished(), `${description} did not finish`).toBeNull();
}

export async function selectStarterTemplate(
  page: Page,
  templateName: string,
): Promise<string> {
  await page.getByTestId(TID.sideNavAllTemplates).click();
  const template = page
    .getByRole("dialog")
    .getByTestId(`template-${templateName.replace(/ /g, "-").toLowerCase()}`);
  await expect(template).toBeVisible({ timeout: TIMEOUTS.standard });

  const placeholderFlowId = new URL(page.url()).pathname.match(
    /\/flow\/([^/?#]+)/,
  )?.[1];
  expect(
    placeholderFlowId,
    "A starter template must be selected from its blank placeholder flow",
  ).toBeTruthy();

  const cleanupResponsePromise = page.waitForResponse(
    (response) => requestDeletesFlow(response.request(), placeholderFlowId!),
    { timeout: TIMEOUTS.standard },
  );
  // Keep an early create/navigation failure from leaving the armed cleanup
  // waiter as an unhandled rejection. Awaiting the original promise below
  // still preserves the exact cleanup failure when this path succeeds.
  void cleanupResponsePromise.catch(() => undefined);
  const [createResponse] = await Promise.all([
    page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname === "/api/v1/flows/",
      // Creating a starter flow does real backend work (template hydration,
      // folder wiring) and can outlive the default action timeout on slow
      // Windows CI runners.
      { timeout: TIMEOUTS.long },
    ),
    template.click(),
  ]);
  expect(
    createResponse.ok(),
    `Creating starter template ${templateName} returned ${createResponse.status()}`,
  ).toBe(true);

  const createdFlow = await createResponse.json();
  const createdFlowId = (createdFlow as { id?: unknown })?.id;
  expect(
    typeof createdFlowId === "string" && createdFlowId.length > 0,
    `Creating starter template ${templateName} returned no flow id`,
  ).toBe(true);

  await page.waitForURL(
    (url) =>
      new RegExp(`^/flow/${createdFlowId}(?:/folder/[^/?#]+)?/?$`).test(
        url.pathname,
      ),
    { timeout: TIMEOUTS.standard },
  );

  const cleanupResponse = await cleanupResponsePromise;
  await assertResponseFinished(cleanupResponse, "Deleting starter placeholder");

  // useDeleteFlow updates the browser store directly and refetches folders; it
  // does not promise a subsequent header-flow request. Perform our own
  // authoritative readback so the helper cannot return with an orphaned blank
  // flow while also avoiding a wait on incidental network activity.
  const inventoryResponse = await page.request.get(
    "/api/v1/flows/?get_all=true&header_flows=true&remove_example_flows=true",
  );
  expect(
    inventoryResponse.ok(),
    `Reading flow inventory returned ${inventoryResponse.status()} ${inventoryResponse.statusText()}`,
  ).toBeTruthy();
  const inventory = await inventoryResponse.json();
  expect(Array.isArray(inventory), "Flow inventory must be an array").toBe(
    true,
  );
  expect(
    (inventory as Array<{ id?: unknown }>).some(
      (flow) => flow?.id === placeholderFlowId,
    ),
    "Starter placeholder remained in the authoritative flow inventory",
  ).toBe(false);

  return createdFlowId as string;
}
